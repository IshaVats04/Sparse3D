# Dataset Preparation Guide

This guide explains how to prepare image datasets for the 3D reconstruction pipeline.

## Quick Start

1. Place your images in `data/raw/`
2. Run validation: `python scripts/validate_images.py data/raw`
3. If validation passes, run the pipeline

## Detailed Instructions

### Option 1: Capture Your Own Images (Recommended for Testing)

The easiest way to test the pipeline is to photograph an object yourself.

#### What You Need

- A smartphone or camera
- An object to reconstruct (mug, toy, sculpture, etc.)
- Good lighting
- A stable surface to place the object

#### Capture Guidelines

1. **Choose a good object**
   - Has texture and details (avoid plain, uniform objects)
   - Fits in frame when photographing from different angles
   - Doesn't move or change shape
   - Examples: ceramic mug, small statue, toy car, plant

2. **Lighting**
   - Use diffuse, even lighting (avoid harsh shadows)
   - Natural light near a window works well
   - Avoid backlighting (light behind the object)
   - Keep lighting consistent across all photos

3. **Camera positioning**
   - Move around the object in a circle
   - Keep the object centered in the frame
   - Maintain similar distance from object in all photos
   - Take photos from multiple heights if possible

4. **Overlap**
   - Each photo should overlap 60-80% with the previous one
   - This ensures features can be matched between images
   - Take more photos than you think you need (10-20 is good)

5. **Photo quality**
   - Keep camera steady (use both hands or a tripod)
   - Use fast shutter speed to avoid motion blur
   - Focus on the object
   - Avoid extreme angles that distort the object

#### Example Capture Sequence

```
1. Start at one side of the object
2. Take a photo
3. Move ~15-20 degrees around the object
4. Take another photo
5. Repeat until you've gone 360 degrees
6. Take photos from above/below if possible
```

#### Transferring Images

1. Copy images from your camera/phone to your computer
2. Rename them if desired (e.g., img001.jpg, img002.jpg, ...)
3. Place them in `data/raw/`

### Option 2: Use Public Datasets

If you prefer to use existing datasets, here are some options:

#### DTU Dataset

**URL**: https://virtual.vtt.fi/vtt-ops/dtu/

**Description**: Multi-view light field dataset with ground truth

**How to use**:
1. Download a scan (e.g., scan24, scan65, scan110)
2. Extract images from the dataset
3. Place images in `data/raw/`
4. Run the pipeline

**Note**: DTU dataset is large and requires significant disk space.

#### ETH3D

**URL**: https://www.eth3d.net/

**Description**: High-quality multi-view stereo benchmark

**How to use**:
1. Download a multi-view dataset (e.g., "delivery_area", "electro")
2. Extract images
3. Place in `data/raw/`

**Note**: Some datasets are very large outdoor scenes.

#### Tanks and Temples

**URL**: http://tanksandtemples.org/

**Description**: Large-scale outdoor scenes

**How to use**:
1. Download a scene (e.g., "Playground", "Truck")
2. Extract images
3. Place in `data/raw/`

**Note**: These are large outdoor scenes, not single objects.

### Option 3: Download Sample Images

If you want a quick test without capturing or downloading large datasets:

1. Search for "multi-view object dataset" online
2. Download a small sample (10-20 images of a single object)
3. Place in `data/raw/`

## Dataset Requirements

### Image Format

Supported formats:
- JPG / JPEG
- PNG
- BMP
- TIFF
- WebP

### Image Count

- **Minimum**: 3 images (will have poor quality)
- **Recommended**: 10-20 images for good baseline
- **Maximum**: No hard limit, but processing time increases

### Image Resolution

- **Minimum**: 64x64 pixels
- **Recommended**: 1920x1080 or higher
- **Maximum**: 8192x8192 (larger will be slow)

### Image Quality

Images should be:
- In focus (no blur)
- Well-exposed (not too dark or bright)
- Free of motion blur
- Consistent lighting across the set

### Content Requirements

Images must show:
- **The same object** in all images
- **Different viewpoints** around the object
- **Sufficient overlap** (60-80%) between consecutive images
- **Good coverage** of the object (ideally 360°)

## Organizing Datasets for Experiments

For the 3/4/5/6/10+ image experiment, organize your data like this:

```
data/
├── raw/                    # Your full dataset (e.g., 20 images)
├── 3_images/              # Subset of 3 images
│   ├── img001.jpg
│   ├── img005.jpg
│   └── img010.jpg
├── 4_images/              # Subset of 4 images
│   ├── img001.jpg
│   ├── img005.jpg
│   ├── img010.jpg
│   └── img015.jpg
├── 5_images/              # Subset of 5 images
├── 6_images/              # Subset of 6 images
└── 10_images/             # Subset of 10 images
```

**Selection strategy**:
- Choose images that are evenly distributed around the object
- Ensure each subset still has good overlap
- Use the same base images, just adding more for larger subsets

## Validation

Before running the pipeline, always validate your dataset:

```bash
python scripts/validate_images.py data/raw
```

This will check:
- Supported formats
- Image dimensions
- Corrupted files
- Duplicates
- Minimum image count

## Troubleshooting Dataset Issues

### Validation Fails

**Problem**: Images fail validation

**Solutions**:
- Check file formats are supported
- Ensure images aren't corrupted
- Verify you have at least 3 images
- Check for exact duplicates

### Reconstruction Fails

**Problem**: COLMAP fails to reconstruct

**Common causes**:
1. **Poor overlap**
   - Solution: Recapture with more overlap between images

2. **Low texture**
   - Solution: Use objects with more visual detail

3. **Lighting changes**
   - Solution: Use consistent lighting across all photos

4. **Camera too far**
   - Solution: Move closer to the object

5. **Insufficient angles**
   - Solution: Capture from more diverse viewpoints

### Poor Quality Results

**Problem**: Reconstruction succeeds but looks bad

**Solutions**:
- Add more images (10-20 instead of 3-6)
- Improve overlap between images
- Capture from more angles (including above/below)
- Ensure good lighting
- Use sharper images (faster shutter, stable camera)

## Example: Preparing a Mug Dataset

Here's a concrete example:

1. **Object**: A ceramic coffee mug with text/design
2. **Setup**: Place mug on a table near a window (natural light)
3. **Capture**:
   - Take 20 photos while walking around the mug
   - Each photo overlaps ~70% with the previous
   - Keep mug centered
   - Maintain ~1 meter distance
4. **Transfer**: Copy photos to `data/raw/`
5. **Validate**: `python scripts/validate_images.py data/raw`
6. **Run**: Start the pipeline

## Tips for Success

1. **Start simple**: Test with 10-20 images first
2. **Use textured objects**: Plain white objects are hard to reconstruct
3. **Good lighting is key**: Avoid harsh shadows and bright highlights
4. **Steady camera**: Blur ruins feature matching
5. **More overlap is better**: 60-80% overlap between consecutive images
6. **Full coverage**: Try to get 360° around the object
7. **Multiple heights**: Capture from above and below if possible

## Checking Your Dataset

After preparing your dataset, verify:

```bash
# Count images
ls data/raw/ | wc -l

# Check file types
ls data/raw/

# Validate
python scripts/validate_images.py data/raw

# View a few images to check quality
# (Use your image viewer)
```

## Next Steps

Once your dataset is ready:

1. Run the validation script
2. Run the complete pipeline (see README.md)
3. Examine the outputs
4. If results are poor, adjust your dataset and try again
5. Once satisfied with the baseline, run the 3/4/5/6/10+ experiment

---

**Remember**: Good input data is essential for good reconstruction. Take time to capture or select high-quality images with good overlap and coverage.
