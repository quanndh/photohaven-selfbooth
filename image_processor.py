"""
High-Quality Image Processor
Applies Lightroom preset adjustments to images using rawpy and Pillow
Maintains highest image quality with proper color management
"""

import rawpy
import numpy as np
from PIL import Image, ImageCms
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import logging
from xmp_parser import XMPPresetParser

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process images with Lightroom presets while maintaining highest quality"""
    
    def __init__(self, preset_path: str, config: Dict[str, Any]):
        self.preset_path = preset_path
        self.config = config
        self.preset_parser = XMPPresetParser(preset_path)
        self.adjustments = self.preset_parser.get_adjustments()
        
        # Color profiles
        self.color_profiles = {
            'sRGB': self._get_srgb_profile(),
            'AdobeRGB': self._get_adobe_rgb_profile(),
            'ProPhotoRGB': self._get_prophoto_rgb_profile(),
        }
    
    def _get_srgb_profile(self) -> Optional[bytes]:
        """Get sRGB ICC profile"""
        try:
            return ImageCms.createProfile('sRGB')
        except:
            return None
    
    def _get_adobe_rgb_profile(self) -> Optional[bytes]:
        """Get Adobe RGB ICC profile"""
        try:
            return ImageCms.createProfile('Adobe RGB')
        except:
            return None
    
    def _get_prophoto_rgb_profile(self) -> Optional[bytes]:
        """Get ProPhoto RGB ICC profile"""
        try:
            return ImageCms.createProfile('ProPhoto RGB')
        except:
            return None
    
    def process_image(self, input_path: str, output_path: str) -> bool:
        """
        Process a single image with the preset
        
        Args:
            input_path: Path to input image
            output_path: Path to save processed image
            
        Returns:
            True if successful, False otherwise
        """
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # Determine if it's a RAW file
            is_raw = input_path.suffix.lower() in [
                ext.lower() for ext in self.config['supported_extensions']['raw']
            ]
            
            if is_raw and self.config.get('raw_processing', True):
                return self._process_raw(input_path, output_path)
            else:
                return self._process_standard(input_path, output_path)
        
        except Exception as e:
            logger.error(f"Error processing {input_path}: {e}", exc_info=True)
            return False
    
    def _process_raw(self, input_path: Path, output_path: Path) -> bool:
        """Process RAW file with rawpy"""
        try:
            # Open RAW file with rawpy
            with rawpy.imread(str(input_path)) as raw:
                # Get raw image data (16-bit)
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    half_size=False,
                    no_auto_bright=False,
                    output_bps=16,  # 16-bit output for maximum quality
                    output_color=rawpy.ColorSpace.sRGB,
                    demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,  # High-quality demosaicing
                    use_auto_wb=False,
                )
            
            # Convert to PIL Image
            # rawpy returns uint16 array, PIL expects it in correct shape
            if rgb.dtype != np.uint16:
                rgb = (rgb * 65535).astype(np.uint16)
            
            # Ensure correct shape: (height, width, channels)
            if len(rgb.shape) == 3 and rgb.shape[2] == 3:
                image = Image.fromarray(rgb, mode='RGB')
            else:
                logger.error(f"Unexpected RAW image shape: {rgb.shape}")
                return False
            
            # Apply preset adjustments
            image = self._apply_adjustments(image)
            
            # Apply color profile
            image = self._apply_color_profile(image)
            
            # Save with maximum quality
            self._save_image(image, output_path)
            
            logger.info(f"Successfully processed RAW: {input_path.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing RAW {input_path}: {e}", exc_info=True)
            return False
    
    def _process_standard(self, input_path: Path, output_path: Path) -> bool:
        """Process standard image format (JPEG, TIFF, PNG)"""
        try:
            # Open image with PIL
            image = Image.open(input_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                if image.mode == 'RGBA':
                    # Create white background for transparency
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3] if image.mode == 'RGBA' else None)
                    image = background
                else:
                    image = image.convert('RGB')
            
            # Preserve original color profile if requested
            if self.config.get('color_profile') == 'preserve':
                # Try to preserve original ICC profile
                if 'icc_profile' in image.info:
                    pass  # Keep original profile
            else:
                # Apply preset adjustments
                image = self._apply_adjustments(image)
                
                # Apply color profile
                image = self._apply_color_profile(image)
            
            # Save with maximum quality
            self._save_image(image, output_path)
            
            logger.info(f"Successfully processed: {input_path.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error processing {input_path}: {e}", exc_info=True)
            return False
    
    def _apply_adjustments(self, image: Image.Image) -> Image.Image:
        """Apply Lightroom preset adjustments to image"""
        # Check if image is 16-bit (from RAW processing)
        img_array_orig = np.array(image)
        is_16bit = img_array_orig.dtype == np.uint16
        
        # Convert to float32 for processing (normalize to 0-1 range)
        if is_16bit:
            img_array = img_array_orig.astype(np.float32) / 65535.0
        else:
            img_array = img_array_orig.astype(np.float32) / 255.0
        
        # Apply exposure
        exposure = self.adjustments.get('Exposure', 0.0)
        if exposure != 0.0:
            img_array = self._apply_exposure(img_array, exposure)
        
        # Apply contrast
        contrast = self.adjustments.get('Contrast', 0.0)
        if contrast != 0.0:
            img_array = self._apply_contrast(img_array, contrast)
        
        # Apply highlights
        highlights = self.adjustments.get('Highlights', 0.0)
        if highlights != 0.0:
            img_array = self._apply_highlights(img_array, highlights)
        
        # Apply shadows
        shadows = self.adjustments.get('Shadows', 0.0)
        if shadows != 0.0:
            img_array = self._apply_shadows(img_array, shadows)
        
        # Apply whites
        whites = self.adjustments.get('Whites', 0.0)
        if whites != 0.0:
            img_array = self._apply_whites(img_array, whites)
        
        # Apply blacks
        blacks = self.adjustments.get('Blacks', 0.0)
        if blacks != 0.0:
            img_array = self._apply_blacks(img_array, blacks)
        
        # Apply clarity
        clarity = self.adjustments.get('Clarity', 0.0)
        if clarity != 0.0:
            img_array = self._apply_clarity(img_array, clarity)
        
        # Apply vibrance
        vibrance = self.adjustments.get('Vibrance', 0.0)
        if vibrance != 0.0:
            img_array = self._apply_vibrance(img_array, vibrance)
        
        # Apply saturation
        saturation = self.adjustments.get('Saturation', 0.0)
        if saturation != 0.0:
            img_array = self._apply_saturation(img_array, saturation)
        
        # Apply temperature and tint
        temperature = self.adjustments.get('Temperature', 0.0)
        tint = self.adjustments.get('Tint', 0.0)
        if temperature != 0.0 or tint != 0.0:
            img_array = self._apply_white_balance(img_array, temperature, tint)
        
        # Convert back to PIL Image
        img_array = np.clip(img_array, 0, 1)
        
        # Convert back to original bit depth
        if is_16bit:
            img_array = (img_array * 65535.0).astype(np.uint16)
        else:
            img_array = (img_array * 255.0).astype(np.uint8)
        
        return Image.fromarray(img_array, mode='RGB')
    
    def _apply_exposure(self, img: np.ndarray, exposure: float) -> np.ndarray:
        """Apply exposure adjustment (in EV stops)"""
        # Convert EV to linear multiplier
        multiplier = 2.0 ** exposure
        return np.clip(img * multiplier, 0, 1)
    
    def _apply_contrast(self, img: np.ndarray, contrast: float) -> np.ndarray:
        """Apply contrast adjustment (-100 to +100)"""
        # Normalize to -1 to 1 range
        contrast_norm = contrast / 100.0
        # Apply contrast curve
        factor = (259 * (contrast_norm + 255)) / (255 * (259 - contrast_norm))
        return np.clip(factor * (img - 0.5) + 0.5, 0, 1)
    
    def _apply_highlights(self, img: np.ndarray, highlights: float) -> np.ndarray:
        """Apply highlights adjustment (-100 to +100)"""
        highlights_norm = highlights / 100.0
        # Compress highlights
        mask = img > 0.5
        img[mask] = 0.5 + (img[mask] - 0.5) * (1 - highlights_norm * 0.5)
        return np.clip(img, 0, 1)
    
    def _apply_shadows(self, img: np.ndarray, shadows: float) -> np.ndarray:
        """Apply shadows adjustment (-100 to +100)"""
        shadows_norm = shadows / 100.0
        # Lift shadows
        mask = img < 0.5
        img[mask] = img[mask] * (1 + shadows_norm)
        return np.clip(img, 0, 1)
    
    def _apply_whites(self, img: np.ndarray, whites: float) -> np.ndarray:
        """Apply whites adjustment (-100 to +100)"""
        whites_norm = whites / 100.0
        # Adjust white point
        white_point = 1.0 - whites_norm * 0.1
        return np.clip(img / white_point, 0, 1)
    
    def _apply_blacks(self, img: np.ndarray, blacks: float) -> np.ndarray:
        """Apply blacks adjustment (-100 to +100)"""
        blacks_norm = blacks / 100.0
        # Adjust black point
        black_point = blacks_norm * 0.1
        return np.clip((img - black_point) / (1 - black_point), 0, 1)
    
    def _apply_clarity(self, img: np.ndarray, clarity: float) -> np.ndarray:
        """Apply clarity adjustment (local contrast enhancement)"""
        if clarity == 0.0:
            return img
        
        clarity_norm = clarity / 100.0
        
        # Simple unsharp mask - use a fast approximation
        # Apply a simple box blur by averaging
        kernel_size = 3
        pad_size = kernel_size // 2
        
        blurred = np.zeros_like(img)
        
        # Apply simple box blur to each channel
        for c in range(3):
            channel = img[:, :, c]
            # Pad the image
            padded = np.pad(channel, pad_size, mode='edge')
            
            # Simple box blur using numpy operations (more efficient)
            h, w = channel.shape
            for i in range(h):
                for j in range(w):
                    # Extract kernel region
                    region = padded[i:i+kernel_size, j:j+kernel_size]
                    blurred[i, j, c] = np.mean(region)
        
        # Create unsharp mask (detail layer)
        detail = img - blurred
        
        # Enhance detail proportionally
        enhanced = img + detail * clarity_norm
        return np.clip(enhanced, 0, 1)
    
    def _apply_vibrance(self, img: np.ndarray, vibrance: float) -> np.ndarray:
        """Apply vibrance adjustment (selective saturation)"""
        vibrance_norm = vibrance / 100.0
        
        # Convert to HSV
        hsv = self._rgb_to_hsv(img)
        
        # Apply vibrance (affects less saturated colors more)
        saturation = hsv[:, :, 1]
        saturation_factor = 1 + vibrance_norm * (1 - saturation)
        hsv[:, :, 1] = np.clip(saturation * saturation_factor, 0, 1)
        
        # Convert back to RGB
        return self._hsv_to_rgb(hsv)
    
    def _apply_saturation(self, img: np.ndarray, saturation: float) -> np.ndarray:
        """Apply saturation adjustment"""
        saturation_norm = saturation / 100.0
        
        # Convert to HSV
        hsv = self._rgb_to_hsv(img)
        
        # Apply saturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1 + saturation_norm), 0, 1)
        
        # Convert back to RGB
        return self._hsv_to_rgb(hsv)
    
    def _apply_white_balance(self, img: np.ndarray, temperature: float, tint: float) -> np.ndarray:
        """Apply white balance adjustment"""
        # Convert temperature to RGB multipliers (simplified)
        # Temperature: -100 (blue) to +100 (yellow)
        # Tint: -150 (green) to +150 (magenta)
        
        temp_factor = temperature / 100.0
        tint_factor = tint / 150.0
        
        # Adjust channels
        img[:, :, 0] *= (1 + temp_factor * 0.1)  # Red
        img[:, :, 1] *= (1 - tint_factor * 0.05)  # Green
        img[:, :, 2] *= (1 - temp_factor * 0.1 + tint_factor * 0.05)  # Blue
        
        return np.clip(img, 0, 1)
    
    def _rgb_to_hsv(self, rgb: np.ndarray) -> np.ndarray:
        """Convert RGB to HSV"""
        hsv = np.zeros_like(rgb)
        max_val = rgb.max(axis=2)
        min_val = rgb.min(axis=2)
        delta = max_val - min_val
        
        # Hue
        hsv[:, :, 0] = np.where(delta == 0, 0,
            np.where(max_val == rgb[:, :, 0],
                ((rgb[:, :, 1] - rgb[:, :, 2]) / delta) % 6,
            np.where(max_val == rgb[:, :, 1],
                2 + (rgb[:, :, 2] - rgb[:, :, 0]) / delta,
                4 + (rgb[:, :, 0] - rgb[:, :, 1]) / delta)) / 6)
        
        # Saturation
        hsv[:, :, 1] = np.where(max_val == 0, 0, delta / max_val)
        
        # Value
        hsv[:, :, 2] = max_val
        
        return hsv
    
    def _hsv_to_rgb(self, hsv: np.ndarray) -> np.ndarray:
        """Convert HSV to RGB"""
        rgb = np.zeros_like(hsv)
        h = hsv[:, :, 0] * 6
        c = hsv[:, :, 2] * hsv[:, :, 1]
        x = c * (1 - np.abs((h % 2) - 1))
        m = hsv[:, :, 2] - c
        
        # Create masks for each hue range
        mask0 = (h >= 0) & (h < 1)
        mask1 = (h >= 1) & (h < 2)
        mask2 = (h >= 2) & (h < 3)
        mask3 = (h >= 3) & (h < 4)
        mask4 = (h >= 4) & (h < 5)
        mask5 = (h >= 5) & (h < 6)
        
        # Apply conversion for each hue range
        rgb[mask0, 0] = c[mask0] + m[mask0]
        rgb[mask0, 1] = x[mask0] + m[mask0]
        rgb[mask0, 2] = m[mask0]
        
        rgb[mask1, 0] = x[mask1] + m[mask1]
        rgb[mask1, 1] = c[mask1] + m[mask1]
        rgb[mask1, 2] = m[mask1]
        
        rgb[mask2, 0] = m[mask2]
        rgb[mask2, 1] = c[mask2] + m[mask2]
        rgb[mask2, 2] = x[mask2] + m[mask2]
        
        rgb[mask3, 0] = m[mask3]
        rgb[mask3, 1] = x[mask3] + m[mask3]
        rgb[mask3, 2] = c[mask3] + m[mask3]
        
        rgb[mask4, 0] = x[mask4] + m[mask4]
        rgb[mask4, 1] = m[mask4]
        rgb[mask4, 2] = c[mask4] + m[mask4]
        
        rgb[mask5, 0] = c[mask5] + m[mask5]
        rgb[mask5, 1] = m[mask5]
        rgb[mask5, 2] = x[mask5] + m[mask5]
        
        return np.clip(rgb, 0, 1)
    
    def _apply_color_profile(self, image: Image.Image) -> Image.Image:
        """Apply color profile to image"""
        color_profile = self.config.get('color_profile', 'sRGB')
        
        if color_profile == 'preserve':
            return image
        
        profile = self.color_profiles.get(color_profile)
        if profile is None:
            logger.warning(f"Color profile {color_profile} not available, using sRGB")
            profile = self.color_profiles.get('sRGB')
        
        if profile is not None:
            try:
                # Convert to target color space
                image = ImageCms.profileToProfile(
                    image,
                    ImageCms.createProfile('sRGB'),
                    profile,
                    outputMode='RGB'
                )
            except Exception as e:
                logger.warning(f"Failed to apply color profile: {e}")
        
        return image
    
    def _save_image(self, image: Image.Image, output_path: Path):
        """Save image with maximum quality"""
        output_format = self.config.get('output_format', 'tiff').lower()
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_format == 'tiff':
            # Save as TIFF for maximum quality
            # Ensure image is RGB mode
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Check if image is 16-bit (from RAW processing)
            # PIL Image doesn't directly expose bit depth, but we can check the mode
            # For 16-bit images, we need to handle them differently
            try:
                # Try to get the array to check bit depth
                img_array = np.array(image)
                if img_array.dtype == np.uint16:
                    # Image is 16-bit, save directly
                    # PIL should handle 16-bit TIFF if the array is uint16
                    image.save(
                        output_path,
                        format='TIFF',
                        compression='lzw',
                    )
                else:
                    # Image is 8-bit, save as 8-bit TIFF
                    image.save(
                        output_path,
                        format='TIFF',
                        compression='lzw',
                    )
            except Exception as e:
                # Fallback: just save as-is
                logger.warning(f"Could not determine bit depth, saving as-is: {e}")
                image.save(
                    output_path,
                    format='TIFF',
                    compression='lzw',
                )
        
        elif output_format == 'jpg' or output_format == 'jpeg':
            # Save as high-quality JPEG
            quality = self.config.get('jpeg_quality', 95)
            image.save(
                output_path,
                format='JPEG',
                quality=quality,
                optimize=True
            )
        
        else:
            # Default to TIFF
            image.save(output_path, format='TIFF', compression='lzw', quality=100)

