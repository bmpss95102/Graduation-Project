{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Mask R-CNN - Train on Shapes Dataset\n",
    "\n",
    "\n",
    "This notebook shows how to train Mask R-CNN on your own dataset. To keep things simple we use a synthetic dataset of shapes (squares, triangles, and circles) which enables fast training. You'd still need a GPU, though, because the network backbone is a Resnet101, which would be too slow to train on a CPU. On a GPU, you can start to get okay-ish results in a few minutes, and good results in less than an hour.\n",
    "\n",
    "The code of the *Shapes* dataset is included below. It generates images on the fly, so it doesn't require downloading any data. And it can generate images of any size, so we pick a small image size to train faster. "
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 1,
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "Using TensorFlow backend.\n"
     ]
    }
   ],
   "source": [
    "import os\n",
    "import sys\n",
    "import random\n",
    "import math\n",
    "import re\n",
    "import time\n",
    "import numpy as np\n",
    "import cv2\n",
    "import matplotlib\n",
    "import matplotlib.pyplot as plt\n",
    "\n",
    "# Root directory of the project\n",
    "ROOT_DIR = os.path.abspath(\"../../\")\n",
    "\n",
    "# Import Mask RCNN\n",
    "sys.path.append(ROOT_DIR)  # To find local version of the library\n",
    "from mrcnn.config import Config\n",
    "from mrcnn import utils\n",
    "import mrcnn.model as modellib\n",
    "from mrcnn import visualize\n",
    "from mrcnn.model import log\n",
    "\n",
    "%matplotlib inline \n",
    "\n",
    "# Directory to save logs and trained model\n",
    "MODEL_DIR = os.path.join(ROOT_DIR, \"logs\")\n",
    "\n",
    "# Local path to trained weights file\n",
    "COCO_MODEL_PATH = os.path.join(ROOT_DIR, \"mask_rcnn_coco.h5\")\n",
    "# Download COCO trained weights from Releases if needed\n",
    "if not os.path.exists(COCO_MODEL_PATH):\n",
    "    utils.download_trained_weights(COCO_MODEL_PATH)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Configurations"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 2,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "\n",
      "Configurations:\n",
      "BACKBONE_SHAPES                [[32 32]\n",
      " [16 16]\n",
      " [ 8  8]\n",
      " [ 4  4]\n",
      " [ 2  2]]\n",
      "BACKBONE_STRIDES               [4, 8, 16, 32, 64]\n",
      "BATCH_SIZE                     8\n",
      "BBOX_STD_DEV                   [ 0.1  0.1  0.2  0.2]\n",
      "DETECTION_MAX_INSTANCES        100\n",
      "DETECTION_MIN_CONFIDENCE       0.5\n",
      "DETECTION_NMS_THRESHOLD        0.3\n",
      "GPU_COUNT                      1\n",
      "IMAGES_PER_GPU                 8\n",
      "IMAGE_MAX_DIM                  128\n",
      "IMAGE_MIN_DIM                  128\n",
      "IMAGE_PADDING                  True\n",
      "IMAGE_SHAPE                    [128 128   3]\n",
      "LEARNING_MOMENTUM              0.9\n",
      "LEARNING_RATE                  0.002\n",
      "MASK_POOL_SIZE                 14\n",
      "MASK_SHAPE                     [28, 28]\n",
      "MAX_GT_INSTANCES               100\n",
      "MEAN_PIXEL                     [ 123.7  116.8  103.9]\n",
      "MINI_MASK_SHAPE                (56, 56)\n",
      "NAME                           SHAPES\n",
      "NUM_CLASSES                    4\n",
      "POOL_SIZE                      7\n",
      "POST_NMS_ROIS_INFERENCE        1000\n",
      "POST_NMS_ROIS_TRAINING         2000\n",
      "ROI_POSITIVE_RATIO             0.33\n",
      "RPN_ANCHOR_RATIOS              [0.5, 1, 2]\n",
      "RPN_ANCHOR_SCALES              (8, 16, 32, 64, 128)\n",
      "RPN_ANCHOR_STRIDE              2\n",
      "RPN_BBOX_STD_DEV               [ 0.1  0.1  0.2  0.2]\n",
      "RPN_TRAIN_ANCHORS_PER_IMAGE    256\n",
      "STEPS_PER_EPOCH                100\n",
      "TRAIN_ROIS_PER_IMAGE           32\n",
      "USE_MINI_MASK                  True\n",
      "USE_RPN_ROIS                   True\n",
      "VALIDATION_STEPS               50\n",
      "WEIGHT_DECAY                   0.0001\n",
      "\n",
      "\n"
     ]
    }
   ],
   "source": [
    "class ShapesConfig(Config):\n",
    "    \"\"\"Configuration for training on the toy shapes dataset.\n",
    "    Derives from the base Config class and overrides values specific\n",
    "    to the toy shapes dataset.\n",
    "    \"\"\"\n",
    "    # Give the configuration a recognizable name\n",
    "    NAME = \"shapes\"\n",
    "\n",
    "    # Train on 1 GPU and 8 images per GPU. We can put multiple images on each\n",
    "    # GPU because the images are small. Batch size is 8 (GPUs * images/GPU).\n",
    "    GPU_COUNT = 1\n",
    "    IMAGES_PER_GPU = 8\n",
    "\n",
    "    # Number of classes (including background)\n",
    "    NUM_CLASSES = 1 + 3  # background + 3 shapes\n",
    "\n",
    "    # Use small images for faster training. Set the limits of the small side\n",
    "    # the large side, and that determines the image shape.\n",
    "    IMAGE_MIN_DIM = 128\n",
    "    IMAGE_MAX_DIM = 128\n",
    "\n",
    "    # Use smaller anchors because our image and objects are small\n",
    "    RPN_ANCHOR_SCALES = (8, 16, 32, 64, 128)  # anchor side in pixels\n",
    "\n",
    "    # Reduce training ROIs per image because the images are small and have\n",
    "    # few objects. Aim to allow ROI sampling to pick 33% positive ROIs.\n",
    "    TRAIN_ROIS_PER_IMAGE = 32\n",
    "\n",
    "    # Use a small epoch since the data is simple\n",
    "    STEPS_PER_EPOCH = 100\n",
    "\n",
    "    # use small validation steps since the epoch is small\n",
    "    VALIDATION_STEPS = 5\n",
    "    \n",
    "config = ShapesConfig()\n",
    "config.display()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Notebook Preferences"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 3,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "def get_ax(rows=1, cols=1, size=8):\n",
    "    \"\"\"Return a Matplotlib Axes array to be used in\n",
    "    all visualizations in the notebook. Provide a\n",
    "    central point to control graph sizes.\n",
    "    \n",
    "    Change the default size attribute to control the size\n",
    "    of rendered images\n",
    "    \"\"\"\n",
    "    _, ax = plt.subplots(rows, cols, figsize=(size*cols, size*rows))\n",
    "    return ax"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Dataset\n",
    "\n",
    "Create a synthetic dataset\n",
    "\n",
    "Extend the Dataset class and add a method to load the shapes dataset, `load_shapes()`, and override the following methods:\n",
    "\n",
    "* load_image()\n",
    "* load_mask()\n",
    "* image_reference()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 4,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "class ShapesDataset(utils.Dataset):\n",
    "    \"\"\"Generates the shapes synthetic dataset. The dataset consists of simple\n",
    "    shapes (triangles, squares, circles) placed randomly on a blank surface.\n",
    "    The images are generated on the fly. No file access required.\n",
    "    \"\"\"\n",
    "\n",
    "    def load_shapes(self, count, height, width):\n",
    "        \"\"\"Generate the requested number of synthetic images.\n",
    "        count: number of images to generate.\n",
    "        height, width: the size of the generated images.\n",
    "        \"\"\"\n",
    "        # Add classes\n",
    "        self.add_class(\"shapes\", 1, \"square\")\n",
    "        self.add_class(\"shapes\", 2, \"circle\")\n",
    "        self.add_class(\"shapes\", 3, \"triangle\")\n",
    "\n",
    "        # Add images\n",
    "        # Generate random specifications of images (i.e. color and\n",
    "        # list of shapes sizes and locations). This is more compact than\n",
    "        # actual images. Images are generated on the fly in load_image().\n",
    "        for i in range(count):\n",
    "            bg_color, shapes = self.random_image(height, width)\n",
    "            self.add_image(\"shapes\", image_id=i, path=None,\n",
    "                           width=width, height=height,\n",
    "                           bg_color=bg_color, shapes=shapes)\n",
    "\n",
    "    def load_image(self, image_id):\n",
    "        \"\"\"Generate an image from the specs of the given image ID.\n",
    "        Typically this function loads the image from a file, but\n",
    "        in this case it generates the image on the fly from the\n",
    "        specs in image_info.\n",
    "        \"\"\"\n",
    "        info = self.image_info[image_id]\n",
    "        bg_color = np.array(info['bg_color']).reshape([1, 1, 3])\n",
    "        image = np.ones([info['height'], info['width'], 3], dtype=np.uint8)\n",
    "        image = image * bg_color.astype(np.uint8)\n",
    "        for shape, color, dims in info['shapes']:\n",
    "            image = self.draw_shape(image, shape, dims, color)\n",
    "        return image\n",
    "\n",
    "    def image_reference(self, image_id):\n",
    "        \"\"\"Return the shapes data of the image.\"\"\"\n",
    "        info = self.image_info[image_id]\n",
    "        if info[\"source\"] == \"shapes\":\n",
    "            return info[\"shapes\"]\n",
    "        else:\n",
    "            super(self.__class__).image_reference(self, image_id)\n",
    "\n",
    "    def load_mask(self, image_id):\n",
    "        \"\"\"Generate instance masks for shapes of the given image ID.\n",
    "        \"\"\"\n",
    "        info = self.image_info[image_id]\n",
    "        shapes = info['shapes']\n",
    "        count = len(shapes)\n",
    "        mask = np.zeros([info['height'], info['width'], count], dtype=np.uint8)\n",
    "        for i, (shape, _, dims) in enumerate(info['shapes']):\n",
    "            mask[:, :, i:i+1] = self.draw_shape(mask[:, :, i:i+1].copy(),\n",
    "                                                shape, dims, 1)\n",
    "        # Handle occlusions\n",
    "        occlusion = np.logical_not(mask[:, :, -1]).astype(np.uint8)\n",
    "        for i in range(count-2, -1, -1):\n",
    "            mask[:, :, i] = mask[:, :, i] * occlusion\n",
    "            occlusion = np.logical_and(occlusion, np.logical_not(mask[:, :, i]))\n",
    "        # Map class names to class IDs.\n",
    "        class_ids = np.array([self.class_names.index(s[0]) for s in shapes])\n",
    "        return mask.astype(np.bool), class_ids.astype(np.int32)\n",
    "\n",
    "    def draw_shape(self, image, shape, dims, color):\n",
    "        \"\"\"Draws a shape from the given specs.\"\"\"\n",
    "        # Get the center x, y and the size s\n",
    "        x, y, s = dims\n",
    "        if shape == 'square':\n",
    "            cv2.rectangle(image, (x-s, y-s), (x+s, y+s), color, -1)\n",
    "        elif shape == \"circle\":\n",
    "            cv2.circle(image, (x, y), s, color, -1)\n",
    "        elif shape == \"triangle\":\n",
    "            points = np.array([[(x, y-s),\n",
    "                                (x-s/math.sin(math.radians(60)), y+s),\n",
    "                                (x+s/math.sin(math.radians(60)), y+s),\n",
    "                                ]], dtype=np.int32)\n",
    "            cv2.fillPoly(image, points, color)\n",
    "        return image\n",
    "\n",
    "    def random_shape(self, height, width):\n",
    "        \"\"\"Generates specifications of a random shape that lies within\n",
    "        the given height and width boundaries.\n",
    "        Returns a tuple of three valus:\n",
    "        * The shape name (square, circle, ...)\n",
    "        * Shape color: a tuple of 3 values, RGB.\n",
    "        * Shape dimensions: A tuple of values that define the shape size\n",
    "                            and location. Differs per shape type.\n",
    "        \"\"\"\n",
    "        # Shape\n",
    "        shape = random.choice([\"square\", \"circle\", \"triangle\"])\n",
    "        # Color\n",
    "        color = tuple([random.randint(0, 255) for _ in range(3)])\n",
    "        # Center x, y\n",
    "        buffer = 20\n",
    "        y = random.randint(buffer, height - buffer - 1)\n",
    "        x = random.randint(buffer, width - buffer - 1)\n",
    "        # Size\n",
    "        s = random.randint(buffer, height//4)\n",
    "        return shape, color, (x, y, s)\n",
    "\n",
    "    def random_image(self, height, width):\n",
    "        \"\"\"Creates random specifications of an image with multiple shapes.\n",
    "        Returns the background color of the image and a list of shape\n",
    "        specifications that can be used to draw the image.\n",
    "        \"\"\"\n",
    "        # Pick random background color\n",
    "        bg_color = np.array([random.randint(0, 255) for _ in range(3)])\n",
    "        # Generate a few random shapes and record their\n",
    "        # bounding boxes\n",
    "        shapes = []\n",
    "        boxes = []\n",
    "        N = random.randint(1, 4)\n",
    "        for _ in range(N):\n",
    "            shape, color, dims = self.random_shape(height, width)\n",
    "            shapes.append((shape, color, dims))\n",
    "            x, y, s = dims\n",
    "            boxes.append([y-s, x-s, y+s, x+s])\n",
    "        # Apply non-max suppression wit 0.3 threshold to avoid\n",
    "        # shapes covering each other\n",
    "        keep_ixs = utils.non_max_suppression(np.array(boxes), np.arange(N), 0.3)\n",
    "        shapes = [s for i, s in enumerate(shapes) if i in keep_ixs]\n",
    "        return bg_color, shapes"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 5,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "# Training dataset\n",
    "dataset_train = ShapesDataset()\n",
    "dataset_train.load_shapes(500, config.IMAGE_SHAPE[0], config.IMAGE_SHAPE[1])\n",
    "dataset_train.prepare()\n",
    "\n",
    "# Validation dataset\n",
    "dataset_val = ShapesDataset()\n",
    "dataset_val.load_shapes(50, config.IMAGE_SHAPE[0], config.IMAGE_SHAPE[1])\n",
    "dataset_val.prepare()"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 6,
   "metadata": {},
   "outputs": [
    {
     "data": {
      "image/png": "iVBORw0KGgoAAAANSUhEUgAAAywAAACnCAYAAADzEdgbAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz\nAAALEgAACxIB0t1+/AAADL9JREFUeJzt3XusZWddx+Hvb6iNCFEpEkRDRFQCjQbU0DIUe1HuluCF\ngopEgQQMvRAkxWAUY4vWUsGkN6PSEjES2xgBiS0ItFhohxawiUJEsdGIQopt00CUtrb+/GOvY3dP\n51xmOuesd2Y/TzKZvdfaZ513z6w5cz77fdc+1d0BAAAY0Z65BwAAALARwQIAAAxLsAAAAMMSLAAA\nwLAECwAAMCzBAgAADGslgqWqvquqPrxu2xcO4jhXVdVTp9svrKrbl/adX1Uv38Yxzqmqf62qv17a\n9rSq+kRVfayqPlJVT5i2f3dV/U1VXVtVH62q79jkuE+sqk9X1Ver6plL23+vqvZV1Q1V9StL299c\nVTdV1Ser6g0H+mcBsB1V9diquuAAHn/tZl/rAFg9KxEsk/U/cOZgfgDNx5OcMN1+ZpLPVNWx0/0T\npv1buSTJyeu2fSnJ87r75CRvT3LOtP11Sd7Z3ackeXeSMzc57peSPDvJn6/bfnF3753G9+Ipgh6Z\n5JXdfdy0/Zeq6uHbGDsrpqpW6WsEO6C7b+3us9dv3+Tc8sPBAHiAVfpmpLZ8QNWlVfXztfDBqnr6\nuodcn+RZ0+2nJvn9JM+qqqOTPLa7/22rz9Hdt2bdf8jd/ZXu/q/p7t1J/me6/bkkj5puH5PkK1V1\ndFV9vKqeNL1yeWNVfXN339Xdd65/nt19y/R7J7k3yX1Jvp7kP6rqEUm+Kcl/L31ODiNVdew0e/bR\nqvqrqnrKdE58oKquqKq3TI/7wtLH/FFVnTjd/mBVXTPNtB0/bfuNqnpXVb0vyWlVdeI0+3dNVV06\nyxPlsFJV5y2dl69Zm+Hez7l18jS7fE1VvX3tw5eO89vTjMv1VfXCOZ4LAPM7au4B7KIfrqprptsb\nxcsbklyTRZR8pLs/tW7/jUkuq6qjkvxvkuuSvCOLsLgpSarqGUnOy4NfJTynuz+22QCngHhrkldN\nmz6S5ENV9eokRyc5rrvvqapXJvnjJHcmOau7v7rZcadjvzzJLWtRVVVXJ/nHLP4s3trd9251DIb0\nvCSXd/c7q6qSvDfJmd19U1X94dLjNnrV+ie7++tV9eQsZv9+bNp+V3f/RJJU1d8mOam7v1ZV76iq\n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\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff54c52e358>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "data": {
      "image/png": "iVBORw0KGgoAAAANSUhEUgAAAywAAACnCAYAAADzEdgbAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz\nAAALEgAACxIB0t1+/AAADBtJREFUeJzt3X/M9XVdx/HXG4lFuCaQmRXLrJyyGlQDFE2gVILZ7Ieu\nmrkyN2gJNHTWbM0WWow5cRO1qYCrVqvWUmKBBoKJ/LrR2AqXRawmSwcBMUxvIOjdH+d74HB539fN\nfcN1nc91zuOxMc75nnN9z+fc9/c+13mez+ecU90dAACAER207AEAAADsjWABAACGJVgAAIBhCRYA\nAGBYggUAABiWYAEAAIa1FsFSVd9TVVdt2Hb7Aezniqo6Zjp9elXdu3DZBVX1+iexj/Oq6j+q6u8W\nth1bVZ+tqk9X1dVV9bxp+/dW1d9X1bVV9amq+s5N9vv8qvpcVT1QVScubH9vVd1YVTdU1W8tbH97\nVe2qqpuq6tz9/bMAeDKq6jlV9e79uP61mz3WAbB+1iJYJhu/cOZAvoDmuiQvnU6fmOTzVXX0dP6l\n0+X78oEkJ2/Y9uUkp3b3yUnek+S8afuvJ7m4u09J8sdJzt5kv19O8ookf7Vh+/u7+yXT+F4zRdAz\nk7yxu4+ftv9aVR36JMbOmqmqdXqMYAt0913d/baN2zc5tnw5GABPsE5PRmqfV6j6YFX9Us18oqqO\n23CV65O8bDp9TJI/TPKyqjokyXO6+0v7uo3uvisbfiF3993d/bXp7ENJ/nc6/YUkh0+nj0hyd1Ud\nUlXXVdULplcub66qb+3uB7v7/o33s7vvmP7fSR5J8miS3Un+s6oOS/ItSb6+cJvsIFV19DR79qmq\n+tuqetF0TFxeVX9RVe+Yrnf7ws98pKpePp3+RFVdM820nTBt+92q+mhVfTzJ66rq5dPs3zVV9cGl\n3FF2lKo6f+G4PGM+w72HY+vkaXb5mqp6z/zHF/bzB9OMy/VVdfoy7gsAy3fwsgewjX60qq6ZTu8t\nXs5Nck1mUXJ1d9+y4fKbk1xSVQcn+b8kn0lyYWZhsStJqurFSc7PN75KeF53f3qzAU4B8a4kvzpt\nujrJJ6vqTUkOSXJ8dz9cVW9M8kdJ7k9yTnc/sNl+p32/Pskd86iqqiuT/Etmfxbv6u5H9rUPhnRq\nkku7++KqqiQfS3J2d++qqg8vXG9vr1r/THfvrqoXZjb79xPT9ge7+6eTpKr+IclJ3f3Vqrqwqk7v\n7iu26P6ww1XVaUmO6u4Tp/PPT/LahassHlv/nOTHuvue6fhd3M+pSZ7V3adMM8A3JnHcAayhdQqW\nz3X3q+ZnqupfN16hux+qqo8muSDJc/dy+d1JfjbJrd19b1V9R2aB89npOjclOWV/BzdF0J8nOb+7\nvzhtviDJb3f3ZVX185mF0Fnd/W9V9e9JDu/um5/Evl+R5JeTvHo6/wNJfi7J85I8I8lnqurj3f2V\n/R03S3dpkt+pqj9J8k9Jvj/JPLRvTvJd0+nFJ4OVJFX1zUneV1UvyCzAF983cMN0nW/L7Di5bHpC\neViSLwb27geTXLtw/tENl8+PrWcnuae770kemwVOHo/rH0py8vRCUyX5pqo6orvv27KRs3aq6s2Z\nBfXt3X3GssfDenIc7ts6Lwn7hlmWqnpukjdlNstx/l72c32S35z+n8zeO/K6TO9fqaoXT0sYFv+7\npqpO3nDbi8seKsmfJvlYd1++4fbmb+y/J9PysKp6ZWaxeU9V/dRm93Va5nNektd298MLlz/Q3Y90\n90NJHkzyzL3cX8b2cHe/rbvfkOSVSe5KMl/KuLik8f5pCeEzkhw7bfvJJI9090mZvV9q8d/Eo0ky\nPZm8I8mru/uU6X1Pl2zd3WEF3JbkpIXzG3/PzI+t/0pyxBTF88fB5PHj8AtJPtndPz69j+8YscLT\nrbs/MD22eZLI0jgO922dZlg2fdP99Mvy0syWWN1SVX9WVad195Ubfu66zJaO3TSdvz7Ja7r7tmTf\nMyxTRf9CkhfW7JPCzkzyI0lOS/LsqnpDkn/s7t9I8vtJPlRVj2T2d3Xm9KrkO5O8KrNXxa+qqs8n\n+WqSv07yoiRHV9UV3f17SS6e7utlVdVJ3trdt1bVLVV14zSsa7t7vz81jSH8YlX9SmZ/x1/JLLYv\nqap7MovcuXcnuSqzJ5N3TdtuTPL26Ti8YZPbeEuSy6d/I49mdvzf9nTeCVZHd185vTflhszeH/eX\nm1z9zUn+pqoeTHJrkrdmemye9vOSqrp22nZnZjPFAKyZenwWHlgl0/uWvq+7z9vnlQEABrVOS8IA\nAIAdxgwLAAAwLDMsAADAsAQLAAAwrKV9Sti5h1xoLdowOoce9eE9XlKV7G3V4O47zzzgW3zvw2/Z\n25d3bqtDf/gsx+Ea233r+5d+HDoGx3Lfrov2uL2qsqcl1N2dI08454Bvb4RjMHEcrjvHISPY7Dhc\np4815gmeGCm1yUPV3i479KgPPXb6qcQLwDItRkpt8mC4p8uq6rGff6rxAsCeCZa183iobBYpT8bi\nz8/jRbgAO8U8NDaLlCdj/vPzeBEuAE8vwbI2nr5Q2ZP5PoULMLqnK1T2pKqEC8DTzJvu18IsVqq2\nJlYWzW9jcbkYwCju23XRY1GxlaoqBx10UO69+X1bejsA60CwrLzHY2U7iRZgNPNY2U6iBeCpEywr\nbTmxMidagFEsI1bmRAvAUyNYVtZyY2VOtADLtsxYmRMtAAdOsKykMWJlTrQAyzJCrMyJFoADI1hW\nzlixMidagO02UqzMiRaA/SdYVsqYsTInWoDtMmKszIkWgP0jWFbMoL+fAbbVqLEyN/r4AEYiWFbG\n418MOTKzLMBWm38x5MjmXy4JwL4JlhWyU16w2ynjBHamnTJ7sVPGCbBsgmUl7IzZFYCtZtYCYPUI\nlhXhhToAsxYAq0iwAAAAwxIsO57lYACJ5WAAq0qwrAArIAAsBwNYVYIFAAAYlmABAACGJVgAAIBh\nCRYAAGBYgmVH8wlhAIlPCANYZYJlR6vsvvOMZQ8CYOmOPOGcZQ8BgC0iWADY8bp72UMAYIsIFgAA\nYFiCBQAAGJZgAQAAhiVYAACAYQmWHa/y9S/5pDCAI44/e9lDAGALCBYAVoJPCgNYTYIFAAAYlmBZ\nCZaFASSWhQGsIsECwMqwLAxg9QiWlbEzZlm6syPGCexcO2GWpbtz+HFnLXsYADuCYGEJatkDAFaY\nWRaA1SJYVsrYsyzdye47xx0fsDpGnmXp7qHHBzCag5c9gHXQSb7239+9bbf3P3nntt3WPnXn2499\nx0KsmF1Zpvt2XbTsISxFd+fIE85Z9jDYRqMtuaqq3LfrIrECcAAEy3ap9X2iLlbGUWt8HMIydbdY\nAThAloSx5cQKwNjL1ABGJljYBmIFAIADI1gAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAA\nYFiCBQAAGJZgAQAAhiVYAACAYQkWAABgWIIFAAAYlmABAACGJVgAAIBhCRYAAGBYggUAABiWYAEA\nAIYlWAAAgGEJFgAAYFiCBQAAGJZgAQAAhiVYAACAYQkWAABgWIIFAAAYlmABAACGJVgAAIBhCRYA\nAGBYggUAABiWYAEAAIYlWAAAgGEJFgAAYFiCBQAAGJZgAQAAhiVYAACAYQkWAABgWIIFAAAYlmAB\nAACGJVgAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAAYFiCBQAAGJZgAQAAhiVYAACAYQkW\nAABgWIIFAAAYlmABAACGJVgAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAAYFiCBQAAGJZg\nAQAAhiVYAACAYQkWAABgWIIFAAAY1sHLHsA6qCSHPevOZQ8DcvhxZy17CAAA+0WwbJNa9gAAAGAH\nsiQMAAAYlmABAACGJVgAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAAYFiCBQAAGJZgAQAA\nhiVYAACAYQkWAABgWIIFAAAYlmABAACGJVgAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAA\nYFiCBQAAGJZgAQAAhiVYAACAYQkWAABgWNXdyx4DAADAHplhAQAAhiVYAACAYQkWAABgWIIFAAAY\nlmABAACGJVgAAIBhCRYAAGBYggUAABiWYAEAAIYlWAAAgGEJFgAAYFiCBQAAGJZgAQAAhiVYAACA\nYQkWAABgWIIFAAAYlmABAACGJVgAAIBhCRYAAGBYggUAABjW/wM61eeL24P+VAAAAABJRU5ErkJg\ngg==\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff46d360fd0>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "data": {
      "image/png": "iVBORw0KGgoAAAANSUhEUgAAAywAAACnCAYAAADzEdgbAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz\nAAALEgAACxIB0t1+/AAADfNJREFUeJzt3X2wbWVdB/DvD+9oilmAhpqVCpnQNJoK5Eu+jIbooPZm\nLwOWSoONiY6oJY7lhJYxmM2I0GRenCKZmpqUwdQU0cS3exGYkvIF7+TohMGAw+goSuDTH3tt2R7O\nueeet7ufvdfnw5y5e6+9Xp51zsNe+7t+z1q7WmsBAADo0SHzbgAAAMBaBBYAAKBbAgsAANAtgQUA\nAOiWwAIAAHRLYAEAALo1isBSVT9RVR9cMe26TaznvVX1iOHxM6vq5pnXzqmqUw5gHWdX1Zeq6gMz\n0x5ZVR+rqo9U1WVV9eBh+kOq6t+q6sNV9aGqeuB+1vvQqvp0VX29qh43M/0vquqTVfWJqvqDmeln\nVdXeqvpUVb18o78LgKr6oap63hqvvbmqjtim7dzlPRyA8RhFYBms/MKZzXwBzRVJHj88flySq6rq\n2OH544fX13N+kievmHZ9kqe31p6c5M+TnD1Mf3GSt7fWnpLkb5OcsZ/1Xp/kaUn+acX0t7bWHju0\n7zlDCLp3khe01o4fpv9uVd3zANrOyFTVmN4j2LgfTvJbKydW1SGttTNbazevssxm+dIwgJEa04eR\nWneGqguq6tSaeH9VHbdilo8necLw+BFJ/jLJE6rq7kmObK19eb1ttNZuyIoDb2vtxtbaN4en30ny\nf8Pj/0xy2PD48CQ3VtXdq+qKqnpYVR1ZVXuq6j6ttW+31m5ZuZ+ttX3Dvy3J7UnuSHJrkv+pqkOT\n3CvJt2a2yQKpqmOH6tmHqupfquqYoU9cWlX/UFV/NMx33cwyf11VTxwev7+qLh8qbScM015XVe+o\nqncneW5VPXGo/l1eVRfMZUfp1ZlJHjX0jb0z/ebXhsrwA6vqiKFyfPnw3nV0kgzzvq2q3jP04fsO\n08+sqiur6u+Gdf747Aar6kHDMpcN/XxbqjgA9GvXvBtwED26qi4fHq8VXl6e5PJMQsllrbUrV7y+\nJ8nuqtqV5LtJPprkzZkEi71JUlU/l+SNuevZwLNbax/ZXwOHAPGGJC8cJl2W5F+r6rQkd09yfGvt\ntqp6QZK/SXJLkpe21r6+v/UO6z4lyb5pqKqq9yX5fCa/ize01m5fbx106elJLmytvb2qKsm7kpzR\nWttbVW+bmW+ts9O/1Fq7taoenkn176nD9G+31n4xSarq6iRPaq19Yxjm88zW2nt3aH9YLG9Ockxr\n7cSqel2S+8/0m9OHeW5JclJr7faqOinJq5P8zvData2106vqrExCzj8mOTXJY5IcmmTfKts8N5P3\n071V9exhfa/aqR0EYP7GFFg+3Vo7cfqkqr6wcobW2neq6h1JzknygDVevzHJLye5prV2c1XdP5OA\n87Fhnk8lecpGGzeEoL9P8sbW2ueGyeckeU1r7ZKq+vVMgtBLWmtfrKr/TnJYa23PAaz7aUl+O8nJ\nw/OfTPIrSR6c5G5JPlpV726tfXWj7WbuLkzy2qq6KMlnkhydZBq09yT50eHxbEivJKmqH0jylqp6\nWCYBfPYaqU8M89w3k35yyRCIDk3yucDqPjHzeNrnDktyflUdmeQeSWZPsFw1/PvlJA9N8pAkn2mt\nfTfJN6rq86ts42eS/NmkO2ZXki9uX/MZm6r6vSS/muS61trp680PO0E/XN+YAsvKqspdqixV9YAk\np2VS5Xhjklessp6PJ/n9JGcNz69P8twkzx/WMa2wzGr5/gpLzW5/+CD4ziTvaq1dumLZ6RjwmzIM\nD6uqX8jkb3dTVT1rlWVm131CJtfEnNRau23m9a8PVZXbq+rbSe69yr7Sv9taa69KkuGi5BuSHJdJ\nxe+4TPpnktwyfGC8KckjM7km6qQkt7fWnlRVxyS5ZGa9dyRJa+2mqtqX5OTW2reG7dxt53eLBXFb\nvv84cscq85ya5OrW2jlV9YxMKtlTs5W/SvKlJD89XDt1aJKfWmV912ZyYuffk++d7IFNaa2dn0l1\nGeZGP1zfmN7o93vR/RAaLsxkiNWVVXVxVT2jtfa+FctdkckB91PD848neU5r7dpk/QrLkKJ/I8nD\na3KnsBcleVSSZyS5X03uuPMfrbWXJfmTJH9VVbdn8rd6UVXdL8nrk5yYyVnxD1bVVUm+keSfkxyT\n5Niqem9r7Y+TvH3Y10uqqiV5RWvtmmGM+CeHZn24tbbhu6bRhd+squdn8jf+aiZhe3dV3ZRJOJk6\nN8kHM/mwd8Mw7ZNJzhr64eyZ8ZXOTHLp8P/IHZn0/2u3cydYWP+b5NZhKNePJJl9H5m+x34gycVV\n9fNJPrvK63dOaO3Gqro4k+rgF5J8JZNQdI+Z2V6ZScXm3sM6Lkxy8fbsDgA9qsm12MCyGa5bOqq1\n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\n3EjpemQAAAAASUVORK5CYII=\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff46d445a90>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    },
    {
     "data": {
      "image/png": "iVBORw0KGgoAAAANSUhEUgAAAywAAACnCAYAAADzEdgbAAAABHNCSVQICAgIfAhkiAAAAAlwSFlz\nAAALEgAACxIB0t1+/AAADmNJREFUeJzt3XuMrHddx/HPt1QiQowtEkRjRFRSiIYWQ8tNaG0LltTg\nBeIFiVIMl9LWIBbFCMaCViBgYqGg9BI1EjVGwCIFekOgt8PlGIWAItFohBTbhkCUgi1f/9hnT4ft\n2d1z9ja/2Xm9mk1nZmdnf3P6nO2+5/s8z1R3BwAAYETHzHsBAAAA6xEsAADAsAQLAAAwLMECAAAM\nS7AAAADDEiwAAMCwliJYqup7quqaNbd9ZguP856qesx0+RlVdcfM515bVc85gse4qKr+vareP3Pb\niVX14ar6QFVdW1UPn27/3qr6+6q6oaquq6rv3OBxH1FVH62qL1XVE2du/4OqurmqbqqqX5+5/RVV\ndaCqbqmqlx7tnwXjq6qHVtXrj+L+N2y0jQEAzMNSBMtk7RvObOUNaD6U5EnT5Scm+VhVPXq6/qTp\n85t5c5JT19z2uSRP7+5Tk7whyUXT7ecmuay7T0vyp0nO3+BxP5fkjCR/veb2N3X3E6b1PXOKoAcl\neV53nzzd/qKqesARrJ0F0t23dfeFa2+vqvX+3ntTJoa0wTYLwBJYpv8J1KZ3qLq0qn6hVry3qh63\n5i43JnnydPkxSd6S5MlVdf8kD+3u/9jse3T3bVnzi2F3f6G7/2e6+tUk/zdd/mSS46bLxyf5QlXd\nv6o+VFWPnF5Bv7WqvrW77+ruL659nt392enfneTuJPck+UqS/6qqByb5liT/O/M9WWBVdfE0Tbuu\nql6wOlmsqt+uqiur6p1Jnl1Vp05Tveur6g2rXz7zOL83TVxurKpnzOO5sDiq6tEz293fVdWjpp9N\nV1XVX1bVq6b7fWbma95WVU+ZLr932hZvqapTptvWbrNPmabQ11fVpXN5ogDMxbHzXsAe+uGqun66\nvF68vDTJ9VmJkmu7+yNrPn9rksur6tgkX0/ywSRvzEpYHEiSqnp8kotz31erL+ruD2y0wCkgXpPk\nnOmma5O8r6qen+T+SU7u7q9V1fOS/EmSLya5oLu/tNHjTo/9nCSfXY2qqro6yT9n5c/iNd1992aP\nwdiq6qwk393dT5yuPyLJs2bucld3/8T0uU8l+ZHuvr2qas3jPD3Jt3X3adPk7eYk79mTJ8GienqS\nK7r7sml7ekeS87v7QFX98cz91pvi/WR3f6WqTsjKFPr06fbZbfbjSZ7a3V+uqjdW1TO623YJsASW\nKVg+2t1PW71SVf+y9g7d/dWqujLJa5M8bJ3PfyHJTyU52N13VNV3ZCVwPjzd55Ykpx3t4qYI+osk\nF3f3p6ebX5vkN7v7XVX1M1kJofO6+1+r6t+SHNfdtx7BY5+R5BeTnD1d/4EkP53k4Unul+SDVfXO\n7v780a6bofxgkhtmrt+z5vM3JUlVPSTJ7d19e3Jo+pbc+8vkDyU5dQr8SvJNVXV8d9+5aytn0V2R\n5Leq6s+S/FOS70+y+oLPrUm+a7o8G8eVJFX1zUn+sKoemZUXgmaPo1rdZr89Kz+v3jUF0QOTfDqw\nTVX1kqy8sPOZ7n7BvNfDcrIdbm6Zdwm7z5Slqh6W5PlZmXJcvM7j3Jjk5dO/k5VjR56d6fiVqnr8\ntCvN7Mf1VXXqmu89u/tNJfnzJO/o7qvWfL/VA/tvz7R7WFWdmZXYvL2qfnyj5zrtXnFRkmd199dm\nPv+l7r67u7+a5K4kD1rn+bI4PpHkqTPX1/79vidJuvu/kxw//RK4uv0l9243n0zyvu7+0en4qceI\nFTbxte6+sLufm+TMJLclWd2ldnbX2i9Ou7LeL8mJ020/luTu7n5qVo7bm/3ZvLrN3p7ks0nO7u7T\npuPvLt+9p8Oy6O43T9uUXxKZG9vh5pZpwrLhQffTL21XZGUXq49U1dur6qzuvnrN130oK7uO3TJd\nvzHJM7v7E8nmE5apon82yQm1cqawFyZ5bJKzkjykqp6b5B+7+1eS/G6SP6qqu7Py3+qF06vjr07y\ntKy8GnlNVX0syZeT/E2SRyV5dFW9p7t/J8ll03N9V1V1kpd198Gq+khV3Twt64buPuqzpjGW7r56\nOjblpqwcl/RXG9z9JUn+tqruSnIwycsy/Z2YHucJVXXDdNt/ZmVCB+v5uar6paxsL5/Pyos+l1fV\n7Vl5sWXV65Nck5W4vm267eYkr5h+Ht60wff41SRXTT+r78nKz+FP7OSTAGBMde/eIACws6bj576v\nuy/a9M4AcBjLtEsYAACwYExYAACAYZmwAAAAwxIsAADAsOZ2lrCzLnm7fdGW2NXn//x6b965px5w\n0nm2wyX2lYNvmvt2aBtcbiNsg4ntcNnZDhnBRtuhCQsAADCsZXofliPTnV9+/e/PexXbdtnLXzHv\n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\niXGIAAAAAElFTkSuQmCC\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff46d208358>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "# Load and display random samples\n",
    "image_ids = np.random.choice(dataset_train.image_ids, 4)\n",
    "for image_id in image_ids:\n",
    "    image = dataset_train.load_image(image_id)\n",
    "    mask, class_ids = dataset_train.load_mask(image_id)\n",
    "    visualize.display_top_masks(image, mask, class_ids, dataset_train.class_names)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Create Model"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "# Create model in training mode\n",
    "model = modellib.MaskRCNN-Original(mode=\"training\", config=config,\n",
    "                          model_dir=MODEL_DIR)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 7,
   "metadata": {
    "collapsed": true,
    "scrolled": false
   },
   "outputs": [],
   "source": [
    "# Which weights to start with?\n",
    "init_with = \"coco\"  # imagenet, coco, or last\n",
    "\n",
    "if init_with == \"imagenet\":\n",
    "    model.load_weights(model.get_imagenet_weights(), by_name=True)\n",
    "elif init_with == \"coco\":\n",
    "    # Load weights trained on MS COCO, but skip layers that\n",
    "    # are different due to the different number of classes\n",
    "    # See README for instructions to download the COCO weights\n",
    "    model.load_weights(COCO_MODEL_PATH, by_name=True,\n",
    "                       exclude=[\"mrcnn_class_logits\", \"mrcnn_bbox_fc\", \n",
    "                                \"mrcnn_bbox\", \"mrcnn_mask\"])\n",
    "elif init_with == \"last\":\n",
    "    # Load the last model you trained and continue training\n",
    "    model.load_weights(model.find_last(), by_name=True)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Training\n",
    "\n",
    "Train in two stages:\n",
    "1. Only the heads. Here we're freezing all the backbone layers and training only the randomly initialized layers (i.e. the ones that we didn't use pre-trained weights from MS COCO). To train only the head layers, pass `layers='heads'` to the `train()` function.\n",
    "\n",
    "2. Fine-tune all layers. For this simple example it's not necessary, but we're including it to show the process. Simply pass `layers=\"all` to train all layers."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 8,
   "metadata": {
    "scrolled": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Checkpoint Path:  /deepmatter/mask_rcnn/logs/shapes2017102802/mask_rcnn_{epoch:04d}.h5\n",
      "Starting at epoch 0. LR=0.002\n",
      "\n",
      "Selecting layers to train\n",
      "fpn_c5p5               (Conv2D)\n",
      "fpn_c4p4               (Conv2D)\n",
      "fpn_c3p3               (Conv2D)\n",
      "fpn_c2p2               (Conv2D)\n",
      "fpn_p5                 (Conv2D)\n",
      "fpn_p2                 (Conv2D)\n",
      "fpn_p3                 (Conv2D)\n",
      "fpn_p4                 (Conv2D)\n",
      "In model:  rpn_model\n",
      "    rpn_conv_shared        (Conv2D)\n",
      "    rpn_class_raw          (Conv2D)\n",
      "    rpn_bbox_pred          (Conv2D)\n",
      "mrcnn_mask_conv1       (TimeDistributed)\n",
      "mrcnn_mask_bn1         (TimeDistributed)\n",
      "mrcnn_mask_conv2       (TimeDistributed)\n",
      "mrcnn_mask_bn2         (TimeDistributed)\n",
      "mrcnn_class_conv1      (TimeDistributed)\n",
      "mrcnn_class_bn1        (TimeDistributed)\n",
      "mrcnn_mask_conv3       (TimeDistributed)\n",
      "mrcnn_mask_bn3         (TimeDistributed)\n",
      "mrcnn_class_conv2      (TimeDistributed)\n",
      "mrcnn_class_bn2        (TimeDistributed)\n",
      "mrcnn_mask_conv4       (TimeDistributed)\n",
      "mrcnn_mask_bn4         (TimeDistributed)\n",
      "mrcnn_bbox_fc          (TimeDistributed)\n",
      "mrcnn_mask_deconv      (TimeDistributed)\n",
      "mrcnn_class_logits     (TimeDistributed)\n",
      "mrcnn_mask             (TimeDistributed)\n"
     ]
    },
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "/usr/local/lib/python3.5/dist-packages/tensorflow/python/ops/gradients_impl.py:95: UserWarning: Converting sparse IndexedSlices to a dense Tensor of unknown shape. This may consume a large amount of memory.\n",
      "  \"Converting sparse IndexedSlices to a dense Tensor of unknown shape. \"\n",
      "/usr/local/lib/python3.5/dist-packages/keras/engine/training.py:1987: UserWarning: Using a generator with `use_multiprocessing=True` and multiple workers may duplicate your data. Please consider using the`keras.utils.Sequence class.\n",
      "  UserWarning('Using a generator with `use_multiprocessing=True`'\n"
     ]
    },
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Epoch 1/1\n",
      "100/100 [==============================] - 73s - loss: 2.2164 - rpn_class_loss: 0.0242 - rpn_bbox_loss: 1.0638 - mrcnn_class_loss: 0.2426 - mrcnn_bbox_loss: 0.3006 - mrcnn_mask_loss: 0.2385 - val_loss: 1.8454 - val_rpn_class_loss: 0.0232 - val_rpn_bbox_loss: 0.9971 - val_mrcnn_class_loss: 0.1398 - val_mrcnn_bbox_loss: 0.1343 - val_mrcnn_mask_loss: 0.2042\n"
     ]
    }
   ],
   "source": [
    "# Train the head branches\n",
    "# Passing layers=\"heads\" freezes all layers except the head\n",
    "# layers. You can also pass a regular expression to select\n",
    "# which layers to train by name pattern.\n",
    "model.train(dataset_train, dataset_val, \n",
    "            learning_rate=config.LEARNING_RATE, \n",
    "            epochs=1, \n",
    "            layers='heads')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 9,
   "metadata": {
    "scrolled": false
   },
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Checkpoint Path:  /deepmatter/mask_rcnn/logs/shapes2017102802/mask_rcnn_{epoch:04d}.h5\n",
      "Starting at epoch 0. LR=0.0002\n",
      "\n",
      "Selecting layers to train\n",
      "conv1                  (Conv2D)\n",
      "bn_conv1               (BatchNorm)\n",
      "res2a_branch2a         (Conv2D)\n",
      "bn2a_branch2a          (BatchNorm)\n",
      "res2a_branch2b         (Conv2D)\n",
      "bn2a_branch2b          (BatchNorm)\n",
      "res2a_branch2c         (Conv2D)\n",
      "res2a_branch1          (Conv2D)\n",
      "bn2a_branch2c          (BatchNorm)\n",
      "bn2a_branch1           (BatchNorm)\n",
      "res2b_branch2a         (Conv2D)\n",
      "bn2b_branch2a          (BatchNorm)\n",
      "res2b_branch2b         (Conv2D)\n",
      "bn2b_branch2b          (BatchNorm)\n",
      "res2b_branch2c         (Conv2D)\n",
      "bn2b_branch2c          (BatchNorm)\n",
      "res2c_branch2a         (Conv2D)\n",
      "bn2c_branch2a          (BatchNorm)\n",
      "res2c_branch2b         (Conv2D)\n",
      "bn2c_branch2b          (BatchNorm)\n",
      "res2c_branch2c         (Conv2D)\n",
      "bn2c_branch2c          (BatchNorm)\n",
      "res3a_branch2a         (Conv2D)\n",
      "bn3a_branch2a          (BatchNorm)\n",
      "res3a_branch2b         (Conv2D)\n",
      "bn3a_branch2b          (BatchNorm)\n",
      "res3a_branch2c         (Conv2D)\n",
      "res3a_branch1          (Conv2D)\n",
      "bn3a_branch2c          (BatchNorm)\n",
      "bn3a_branch1           (BatchNorm)\n",
      "res3b_branch2a         (Conv2D)\n",
      "bn3b_branch2a          (BatchNorm)\n",
      "res3b_branch2b         (Conv2D)\n",
      "bn3b_branch2b          (BatchNorm)\n",
      "res3b_branch2c         (Conv2D)\n",
      "bn3b_branch2c          (BatchNorm)\n",
      "res3c_branch2a         (Conv2D)\n",
      "bn3c_branch2a          (BatchNorm)\n",
      "res3c_branch2b         (Conv2D)\n",
      "bn3c_branch2b          (BatchNorm)\n",
      "res3c_branch2c         (Conv2D)\n",
      "bn3c_branch2c          (BatchNorm)\n",
      "res3d_branch2a         (Conv2D)\n",
      "bn3d_branch2a          (BatchNorm)\n",
      "res3d_branch2b         (Conv2D)\n",
      "bn3d_branch2b          (BatchNorm)\n",
      "res3d_branch2c         (Conv2D)\n",
      "bn3d_branch2c          (BatchNorm)\n",
      "res4a_branch2a         (Conv2D)\n",
      "bn4a_branch2a          (BatchNorm)\n",
      "res4a_branch2b         (Conv2D)\n",
      "bn4a_branch2b          (BatchNorm)\n",
      "res4a_branch2c         (Conv2D)\n",
      "res4a_branch1          (Conv2D)\n",
      "bn4a_branch2c          (BatchNorm)\n",
      "bn4a_branch1           (BatchNorm)\n",
      "res4b_branch2a         (Conv2D)\n",
      "bn4b_branch2a          (BatchNorm)\n",
      "res4b_branch2b         (Conv2D)\n",
      "bn4b_branch2b          (BatchNorm)\n",
      "res4b_branch2c         (Conv2D)\n",
      "bn4b_branch2c          (BatchNorm)\n",
      "res4c_branch2a         (Conv2D)\n",
      "bn4c_branch2a          (BatchNorm)\n",
      "res4c_branch2b         (Conv2D)\n",
      "bn4c_branch2b          (BatchNorm)\n",
      "res4c_branch2c         (Conv2D)\n",
      "bn4c_branch2c          (BatchNorm)\n",
      "res4d_branch2a         (Conv2D)\n",
      "bn4d_branch2a          (BatchNorm)\n",
      "res4d_branch2b         (Conv2D)\n",
      "bn4d_branch2b          (BatchNorm)\n",
      "res4d_branch2c         (Conv2D)\n",
      "bn4d_branch2c          (BatchNorm)\n",
      "res4e_branch2a         (Conv2D)\n",
      "bn4e_branch2a          (BatchNorm)\n",
      "res4e_branch2b         (Conv2D)\n",
      "bn4e_branch2b          (BatchNorm)\n",
      "res4e_branch2c         (Conv2D)\n",
      "bn4e_branch2c          (BatchNorm)\n",
      "res4f_branch2a         (Conv2D)\n",
      "bn4f_branch2a          (BatchNorm)\n",
      "res4f_branch2b         (Conv2D)\n",
      "bn4f_branch2b          (BatchNorm)\n",
      "res4f_branch2c         (Conv2D)\n",
      "bn4f_branch2c          (BatchNorm)\n",
      "res4g_branch2a         (Conv2D)\n",
      "bn4g_branch2a          (BatchNorm)\n",
      "res4g_branch2b         (Conv2D)\n",
      "bn4g_branch2b          (BatchNorm)\n",
      "res4g_branch2c         (Conv2D)\n",
      "bn4g_branch2c          (BatchNorm)\n",
      "res4h_branch2a         (Conv2D)\n",
      "bn4h_branch2a          (BatchNorm)\n",
      "res4h_branch2b         (Conv2D)\n",
      "bn4h_branch2b          (BatchNorm)\n",
      "res4h_branch2c         (Conv2D)\n",
      "bn4h_branch2c          (BatchNorm)\n",
      "res4i_branch2a         (Conv2D)\n",
      "bn4i_branch2a          (BatchNorm)\n",
      "res4i_branch2b         (Conv2D)\n",
      "bn4i_branch2b          (BatchNorm)\n",
      "res4i_branch2c         (Conv2D)\n",
      "bn4i_branch2c          (BatchNorm)\n",
      "res4j_branch2a         (Conv2D)\n",
      "bn4j_branch2a          (BatchNorm)\n",
      "res4j_branch2b         (Conv2D)\n",
      "bn4j_branch2b          (BatchNorm)\n",
      "res4j_branch2c         (Conv2D)\n",
      "bn4j_branch2c          (BatchNorm)\n",
      "res4k_branch2a         (Conv2D)\n",
      "bn4k_branch2a          (BatchNorm)\n",
      "res4k_branch2b         (Conv2D)\n",
      "bn4k_branch2b          (BatchNorm)\n",
      "res4k_branch2c         (Conv2D)\n",
      "bn4k_branch2c          (BatchNorm)\n",
      "res4l_branch2a         (Conv2D)\n",
      "bn4l_branch2a          (BatchNorm)\n",
      "res4l_branch2b         (Conv2D)\n",
      "bn4l_branch2b          (BatchNorm)\n",
      "res4l_branch2c         (Conv2D)\n",
      "bn4l_branch2c          (BatchNorm)\n",
      "res4m_branch2a         (Conv2D)\n",
      "bn4m_branch2a          (BatchNorm)\n",
      "res4m_branch2b         (Conv2D)\n",
      "bn4m_branch2b          (BatchNorm)\n",
      "res4m_branch2c         (Conv2D)\n",
      "bn4m_branch2c          (BatchNorm)\n",
      "res4n_branch2a         (Conv2D)\n",
      "bn4n_branch2a          (BatchNorm)\n",
      "res4n_branch2b         (Conv2D)\n",
      "bn4n_branch2b          (BatchNorm)\n",
      "res4n_branch2c         (Conv2D)\n",
      "bn4n_branch2c          (BatchNorm)\n",
      "res4o_branch2a         (Conv2D)\n",
      "bn4o_branch2a          (BatchNorm)\n",
      "res4o_branch2b         (Conv2D)\n",
      "bn4o_branch2b          (BatchNorm)\n",
      "res4o_branch2c         (Conv2D)\n",
      "bn4o_branch2c          (BatchNorm)\n",
      "res4p_branch2a         (Conv2D)\n",
      "bn4p_branch2a          (BatchNorm)\n",
      "res4p_branch2b         (Conv2D)\n",
      "bn4p_branch2b          (BatchNorm)\n",
      "res4p_branch2c         (Conv2D)\n",
      "bn4p_branch2c          (BatchNorm)\n",
      "res4q_branch2a         (Conv2D)\n",
      "bn4q_branch2a          (BatchNorm)\n",
      "res4q_branch2b         (Conv2D)\n",
      "bn4q_branch2b          (BatchNorm)\n",
      "res4q_branch2c         (Conv2D)\n",
      "bn4q_branch2c          (BatchNorm)\n",
      "res4r_branch2a         (Conv2D)\n",
      "bn4r_branch2a          (BatchNorm)\n",
      "res4r_branch2b         (Conv2D)\n",
      "bn4r_branch2b          (BatchNorm)\n",
      "res4r_branch2c         (Conv2D)\n",
      "bn4r_branch2c          (BatchNorm)\n",
      "res4s_branch2a         (Conv2D)\n",
      "bn4s_branch2a          (BatchNorm)\n",
      "res4s_branch2b         (Conv2D)\n",
      "bn4s_branch2b          (BatchNorm)\n",
      "res4s_branch2c         (Conv2D)\n",
      "bn4s_branch2c          (BatchNorm)\n",
      "res4t_branch2a         (Conv2D)\n",
      "bn4t_branch2a          (BatchNorm)\n",
      "res4t_branch2b         (Conv2D)\n",
      "bn4t_branch2b          (BatchNorm)\n",
      "res4t_branch2c         (Conv2D)\n",
      "bn4t_branch2c          (BatchNorm)\n",
      "res4u_branch2a         (Conv2D)\n",
      "bn4u_branch2a          (BatchNorm)\n",
      "res4u_branch2b         (Conv2D)\n",
      "bn4u_branch2b          (BatchNorm)\n",
      "res4u_branch2c         (Conv2D)\n",
      "bn4u_branch2c          (BatchNorm)\n",
      "res4v_branch2a         (Conv2D)\n",
      "bn4v_branch2a          (BatchNorm)\n",
      "res4v_branch2b         (Conv2D)\n",
      "bn4v_branch2b          (BatchNorm)\n",
      "res4v_branch2c         (Conv2D)\n",
      "bn4v_branch2c          (BatchNorm)\n",
      "res4w_branch2a         (Conv2D)\n",
      "bn4w_branch2a          (BatchNorm)\n",
      "res4w_branch2b         (Conv2D)\n",
      "bn4w_branch2b          (BatchNorm)\n",
      "res4w_branch2c         (Conv2D)\n",
      "bn4w_branch2c          (BatchNorm)\n",
      "res5a_branch2a         (Conv2D)\n",
      "bn5a_branch2a          (BatchNorm)\n",
      "res5a_branch2b         (Conv2D)\n",
      "bn5a_branch2b          (BatchNorm)\n",
      "res5a_branch2c         (Conv2D)\n",
      "res5a_branch1          (Conv2D)\n",
      "bn5a_branch2c          (BatchNorm)\n",
      "bn5a_branch1           (BatchNorm)\n",
      "res5b_branch2a         (Conv2D)\n",
      "bn5b_branch2a          (BatchNorm)\n",
      "res5b_branch2b         (Conv2D)\n",
      "bn5b_branch2b          (BatchNorm)\n",
      "res5b_branch2c         (Conv2D)\n",
      "bn5b_branch2c          (BatchNorm)\n",
      "res5c_branch2a         (Conv2D)\n",
      "bn5c_branch2a          (BatchNorm)\n",
      "res5c_branch2b         (Conv2D)\n",
      "bn5c_branch2b          (BatchNorm)\n",
      "res5c_branch2c         (Conv2D)\n",
      "bn5c_branch2c          (BatchNorm)\n",
      "fpn_c5p5               (Conv2D)\n",
      "fpn_c4p4               (Conv2D)\n",
      "fpn_c3p3               (Conv2D)\n",
      "fpn_c2p2               (Conv2D)\n",
      "fpn_p5                 (Conv2D)\n",
      "fpn_p2                 (Conv2D)\n",
      "fpn_p3                 (Conv2D)\n",
      "fpn_p4                 (Conv2D)\n",
      "In model:  rpn_model\n",
      "    rpn_conv_shared        (Conv2D)\n",
      "    rpn_class_raw          (Conv2D)\n",
      "    rpn_bbox_pred          (Conv2D)\n",
      "mrcnn_mask_conv1       (TimeDistributed)\n",
      "mrcnn_mask_bn1         (TimeDistributed)\n",
      "mrcnn_mask_conv2       (TimeDistributed)\n",
      "mrcnn_mask_bn2         (TimeDistributed)\n",
      "mrcnn_class_conv1      (TimeDistributed)\n",
      "mrcnn_class_bn1        (TimeDistributed)\n",
      "mrcnn_mask_conv3       (TimeDistributed)\n",
      "mrcnn_mask_bn3         (TimeDistributed)\n",
      "mrcnn_class_conv2      (TimeDistributed)\n",
      "mrcnn_class_bn2        (TimeDistributed)\n",
      "mrcnn_mask_conv4       (TimeDistributed)\n",
      "mrcnn_mask_bn4         (TimeDistributed)\n",
      "mrcnn_bbox_fc          (TimeDistributed)\n",
      "mrcnn_mask_deconv      (TimeDistributed)\n",
      "mrcnn_class_logits     (TimeDistributed)\n",
      "mrcnn_mask             (TimeDistributed)\n"
     ]
    },
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "/usr/local/lib/python3.5/dist-packages/tensorflow/python/ops/gradients_impl.py:95: UserWarning: Converting sparse IndexedSlices to a dense Tensor of unknown shape. This may consume a large amount of memory.\n",
      "  \"Converting sparse IndexedSlices to a dense Tensor of unknown shape. \"\n",
      "/usr/local/lib/python3.5/dist-packages/keras/engine/training.py:1987: UserWarning: Using a generator with `use_multiprocessing=True` and multiple workers may duplicate your data. Please consider using the`keras.utils.Sequence class.\n",
      "  UserWarning('Using a generator with `use_multiprocessing=True`'\n"
     ]
    },
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Epoch 1/1\n",
      "100/100 [==============================] - 86s - loss: 11.4006 - rpn_class_loss: 0.0184 - rpn_bbox_loss: 0.8409 - mrcnn_class_loss: 0.1576 - mrcnn_bbox_loss: 0.0902 - mrcnn_mask_loss: 0.1977 - val_loss: 11.4376 - val_rpn_class_loss: 0.0220 - val_rpn_bbox_loss: 1.0068 - val_mrcnn_class_loss: 0.1172 - val_mrcnn_bbox_loss: 0.0683 - val_mrcnn_mask_loss: 0.1278\n"
     ]
    }
   ],
   "source": [
    "# Fine tune all layers\n",
    "# Passing layers=\"all\" trains all layers. You can also \n",
    "# pass a regular expression to select which layers to\n",
    "# train by name pattern.\n",
    "model.train(dataset_train, dataset_val, \n",
    "            learning_rate=config.LEARNING_RATE / 10,\n",
    "            epochs=2, \n",
    "            layers=\"all\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 10,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "# Save weights\n",
    "# Typically not needed because callbacks save after every epoch\n",
    "# Uncomment to save manually\n",
    "# model_path = os.path.join(MODEL_DIR, \"mask_rcnn_shapes.h5\")\n",
    "# model.keras_model.save_weights(model_path)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Detection"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 11,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "class InferenceConfig(ShapesConfig):\n",
    "    GPU_COUNT = 1\n",
    "    IMAGES_PER_GPU = 1\n",
    "\n",
    "inference_config = InferenceConfig()\n",
    "\n",
    "# Recreate the model in inference mode\n",
    "model = modellib.MaskRCNN-Original(mode=\"inference\", \n",
    "                          config=inference_config,\n",
    "                          model_dir=MODEL_DIR)\n",
    "\n",
    "# Get path to saved weights\n",
    "# Either set a specific path or find last trained weights\n",
    "# model_path = os.path.join(ROOT_DIR, \".h5 file name here\")\n",
    "model_path = model.find_last()\n",
    "\n",
    "# Load trained weights\n",
    "print(\"Loading weights from \", model_path)\n",
    "model.load_weights(model_path, by_name=True)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 12,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "original_image           shape: (128, 128, 3)         min:  108.00000  max:  236.00000\n",
      "image_meta               shape: (12,)                 min:    0.00000  max:  128.00000\n",
      "gt_bbox                  shape: (2, 5)                min:    2.00000  max:  102.00000\n",
      "gt_mask                  shape: (128, 128, 2)         min:    0.00000  max:    1.00000\n"
     ]
    },
    {
     "data": {
      "image/png": "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\nLwAAAABJRU5ErkJggg==\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff36b5de278>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "# Test on a random image\n",
    "image_id = random.choice(dataset_val.image_ids)\n",
    "original_image, image_meta, gt_class_id, gt_bbox, gt_mask =\\\n",
    "    modellib.load_image_gt(dataset_val, inference_config, \n",
    "                           image_id, use_mini_mask=False)\n",
    "\n",
    "log(\"original_image\", original_image)\n",
    "log(\"image_meta\", image_meta)\n",
    "log(\"gt_class_id\", gt_class_id)\n",
    "log(\"gt_bbox\", gt_bbox)\n",
    "log(\"gt_mask\", gt_mask)\n",
    "\n",
    "visualize.display_instances(original_image, gt_bbox, gt_mask, gt_class_id, \n",
    "                            dataset_train.class_names, figsize=(8, 8))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 13,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "Processing 1 images\n",
      "image                    shape: (128, 128, 3)         min:  108.00000  max:  236.00000\n",
      "molded_images            shape: (1, 128, 128, 3)      min:  -15.70000  max:  132.10000\n",
      "image_metas              shape: (1, 12)               min:    0.00000  max:  128.00000\n"
     ]
    },
    {
     "data": {
      "image/png": "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\n",
      "text/plain": [
       "<matplotlib.figure.Figure at 0x7ff36b5de080>"
      ]
     },
     "metadata": {},
     "output_type": "display_data"
    }
   ],
   "source": [
    "results = model.detect([original_image], verbose=1)\n",
    "\n",
    "r = results[0]\n",
    "visualize.display_instances(original_image, r['rois'], r['masks'], r['class_ids'], \n",
    "                            dataset_val.class_names, r['scores'], ax=get_ax())"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Evaluation"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 14,
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "mAP:  0.95\n"
     ]
    }
   ],
   "source": [
    "# Compute VOC-Style mAP @ IoU=0.5\n",
    "# Running on 10 images. Increase for better accuracy.\n",
    "image_ids = np.random.choice(dataset_val.image_ids, 10)\n",
    "APs = []\n",
    "for image_id in image_ids:\n",
    "    # Load image and ground truth data\n",
    "    image, image_meta, gt_class_id, gt_bbox, gt_mask =\\\n",
    "        modellib.load_image_gt(dataset_val, inference_config,\n",
    "                               image_id, use_mini_mask=False)\n",
    "    molded_images = np.expand_dims(modellib.mold_image(image, inference_config), 0)\n",
    "    # Run object detection\n",
    "    results = model.detect([image], verbose=0)\n",
    "    r = results[0]\n",
    "    # Compute AP\n",
    "    AP, precisions, recalls, overlaps =\\\n",
    "        utils.compute_ap(gt_bbox, gt_class_id, gt_mask,\n",
    "                         r[\"rois\"], r[\"class_ids\"], r[\"scores\"], r['masks'])\n",
    "    APs.append(AP)\n",
    "    \n",
    "print(\"mAP: \", np.mean(APs))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": []
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.6.2"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}
