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
        logger.debug(f"Loaded adjustments: {list(self.adjustments.keys())}")
        # Log key brightness/contrast adjustments
        logger.info(f"Exposure2012: {self.adjustments.get('Exposure2012', self.adjustments.get('Exposure', 0.0))}")
        logger.info(f"Contrast2012: {self.adjustments.get('Contrast2012', self.adjustments.get('Contrast', 0.0))}")
        logger.info(f"Shadows2012: {self.adjustments.get('Shadows2012', self.adjustments.get('Shadows', 0.0))}")
        logger.info(f"Blacks2012: {self.adjustments.get('Blacks2012', self.adjustments.get('Blacks', 0.0))}")
        logger.info(f"Whites2012: {self.adjustments.get('Whites2012', self.adjustments.get('Whites', 0.0))}")
        logger.info(f"Highlights2012: {self.adjustments.get('Highlights2012', self.adjustments.get('Highlights', 0.0))}")
        logger.info(f"ColorGradeMidtoneHue: {self.adjustments.get('ColorGradeMidtoneHue')}")
        logger.info(f"ColorGradeMidtoneSat: {self.adjustments.get('ColorGradeMidtoneSat')}")
        logger.info(f"ColorGradeMidtoneLum: {self.adjustments.get('ColorGradeMidtoneLum', 0.0)}")
        
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
        """Get Adobe RGB ICC profile
        
        Tries multiple methods:
        1. Create profile using ImageCms
        2. Load from common system locations
        3. Try alternative profile names
        """
        # Method 1: Try creating profile directly
        try:
            profile = ImageCms.createProfile('Adobe RGB')
            if profile:
                return profile
        except Exception as e:
            logger.debug(f"Could not create Adobe RGB profile: {e}")
        
        # Method 2: Try alternative names
        alternative_names = [
            'AdobeRGB1998',
            'Adobe RGB (1998)',
            'AdobeRGB',
            'adobe-rgb',
        ]
        for name in alternative_names:
            try:
                profile = ImageCms.createProfile(name)
                if profile:
                    logger.info(f"Found Adobe RGB profile as '{name}'")
                    return profile
            except:
                continue
        
        # Method 3: Try loading from common system ICC directories
        import os
        icc_paths = [
            '/System/Library/ColorSync/Profiles/Adobe RGB (1998).icc',  # macOS
            '/usr/share/color/icc/AdobeRGB1998.icc',  # Linux
            'C:/Windows/System32/spool/drivers/color/AdobeRGB1998.icc',  # Windows
            'C:/Program Files/Common Files/Adobe/Color/Profiles/AdobeRGB1998.icc',  # Windows Adobe
        ]
        
        for icc_path in icc_paths:
            if os.path.exists(icc_path):
                try:
                    with open(icc_path, 'rb') as f:
                        profile_data = f.read()
                    logger.info(f"Loaded Adobe RGB profile from: {icc_path}")
                    return profile_data
                except Exception as e:
                    logger.debug(f"Could not load profile from {icc_path}: {e}")
                    continue
        
        logger.warning("Adobe RGB profile not found. Using sRGB instead.")
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
            print(f"Processing image: {input_path} -> {output_path}")
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
        
        # Apply exposure (prefer 2012 version if available)
        exposure = self.adjustments.get('Exposure2012', self.adjustments.get('Exposure', 0.0))
        if exposure != 0.0:
            img_array = self._apply_exposure(img_array, exposure)
        
        # Apply contrast (prefer 2012 version if available)
        contrast = self.adjustments.get('Contrast2012', self.adjustments.get('Contrast', 0.0))
        if contrast != 0.0:
            img_array = self._apply_contrast(img_array, contrast)
        
        # Apply highlights (prefer 2012 version if available)
        highlights = self.adjustments.get('Highlights2012', self.adjustments.get('Highlights', 0.0))
        if highlights != 0.0:
            img_array = self._apply_highlights(img_array, highlights)
        
        # Apply shadows (prefer 2012 version if available)
        shadows = self.adjustments.get('Shadows2012', self.adjustments.get('Shadows', 0.0))
        if shadows != 0.0:
            img_array = self._apply_shadows(img_array, shadows)
        
        # Apply whites (prefer 2012 version if available)
        whites = self.adjustments.get('Whites2012', self.adjustments.get('Whites', 0.0))
        if whites != 0.0:
            img_array = self._apply_whites(img_array, whites)
        
        # Apply blacks (prefer 2012 version if available)
        blacks = self.adjustments.get('Blacks2012', self.adjustments.get('Blacks', 0.0))
        if blacks != 0.0:
            img_array = self._apply_blacks(img_array, blacks)
        
        # Apply clarity (prefer 2012 version if available)
        clarity = self.adjustments.get('Clarity2012', self.adjustments.get('Clarity', 0.0))
        if clarity != 0.0:
            img_array = self._apply_clarity(img_array, clarity)
        
        # TEMPORARILY DISABLED - Texture and Dehaze
        # # Apply texture
        # texture = self.adjustments.get('Texture', 0.0)
        # if texture != 0.0:
        #     img_array = self._apply_texture(img_array, texture)
        # 
        # # Apply dehaze
        # dehaze = self.adjustments.get('Dehaze', 0.0)
        # if dehaze != 0.0:
        #     img_array = self._apply_dehaze(img_array, dehaze)
        
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
        
        # Apply tone curves (if present)
        # Tone curves are applied after other adjustments
        # Tone curves can significantly affect overall brightness!
        tone_curve = self.adjustments.get('ToneCurve')
        if tone_curve:
            logger.info(f"Applying tone curve with {len(tone_curve)} points")
            img_array = self._apply_tone_curve(img_array, tone_curve)
        
        # Apply per-channel tone curves if present
        tone_curve_red = self.adjustments.get('ToneCurveRed')
        tone_curve_green = self.adjustments.get('ToneCurveGreen')
        tone_curve_blue = self.adjustments.get('ToneCurveBlue')
        if tone_curve_red or tone_curve_green or tone_curve_blue:
            img_array = self._apply_channel_tone_curves(
                img_array, tone_curve_red, tone_curve_green, tone_curve_blue
            )
        
        # TEMPORARILY DISABLED - HSL adjustments (causing corruption)
        # # Apply HSL adjustments (per-color adjustments)
        # logger.debug("Applying HSL adjustments")
        # img_array = self._apply_hsl_adjustments(img_array)
        # logger.debug("HSL adjustments complete")
        
        # Apply split toning (applied before color grading in Lightroom)
        split_shadow_hue = self.adjustments.get('SplitToningShadowHue')
        split_shadow_sat = self.adjustments.get('SplitToningShadowSaturation', 0.0)
        split_highlight_hue = self.adjustments.get('SplitToningHighlightHue')
        split_highlight_sat = self.adjustments.get('SplitToningHighlightSaturation', 0.0)
        split_balance = self.adjustments.get('SplitToningBalance', 0.0)
        if (split_shadow_hue is not None and split_shadow_sat > 0) or (split_highlight_hue is not None and split_highlight_sat > 0):
            logger.debug("Applying split toning")
            img_array = self._apply_split_toning(
                img_array, split_shadow_hue, split_shadow_sat,
                split_highlight_hue, split_highlight_sat, split_balance
            )
            logger.debug("Split toning complete")
        
        # Apply color grading (this is what creates the yellow tone!)
        # Color grading is applied last and affects hue/saturation/luminance in shadows/midtones/highlights
        color_grade_midtone_hue = self.adjustments.get('ColorGradeMidtoneHue')
        color_grade_midtone_sat = self.adjustments.get('ColorGradeMidtoneSat', 0.0)
        color_grade_shadow_lum = self.adjustments.get('ColorGradeShadowLum', 0.0)
        color_grade_midtone_lum = self.adjustments.get('ColorGradeMidtoneLum', 0.0)
        color_grade_highlight_lum = self.adjustments.get('ColorGradeHighlightLum', 0.0)
        color_grade_blending = self.adjustments.get('ColorGradeBlending', 50.0)
        if color_grade_midtone_hue is not None or color_grade_shadow_lum != 0.0 or color_grade_midtone_lum != 0.0 or color_grade_highlight_lum != 0.0:
            logger.debug(f"Applying color grading: midtone_hue={color_grade_midtone_hue}")
            img_array = self._apply_color_grading(
                img_array, color_grade_midtone_hue, color_grade_midtone_sat,
                color_grade_shadow_lum, color_grade_midtone_lum, color_grade_highlight_lum,
                color_grade_blending
            )
            logger.debug("Color grading complete")
        
        # Convert back to PIL Image
        img_array = np.clip(img_array, 0, 1)
        
        # Convert back to original bit depth
        if is_16bit:
            img_array = (img_array * 65535.0).astype(np.uint16)
        else:
            img_array = (img_array * 255.0).astype(np.uint8)
        
        # Ensure array has correct shape (height, width, channels)
        if len(img_array.shape) != 3 or img_array.shape[2] != 3:
            logger.error(f"Invalid image array shape: {img_array.shape}")
            # Try to fix if possible
            if len(img_array.shape) == 2:
                # Grayscale, convert to RGB
                img_array = np.stack([img_array, img_array, img_array], axis=2)
            elif img_array.shape[2] != 3:
                logger.error(f"Cannot fix array shape: {img_array.shape}")
                return image  # Return original if we can't fix it
        
        # Ensure contiguous array for PIL
        img_array = np.ascontiguousarray(img_array)
        
        return Image.fromarray(img_array, mode='RGB')
    
    def _apply_exposure(self, img: np.ndarray, exposure: float) -> np.ndarray:
        """Apply exposure adjustment (in EV stops)"""
        # Convert EV to linear multiplier
        multiplier = 2.0 ** exposure
        return np.clip(img * multiplier, 0, 1)
    
    def _apply_contrast(self, img: np.ndarray, contrast: float) -> np.ndarray:
        """Apply contrast adjustment (-100 to +100)
        
        Lightroom 2012 uses a more sophisticated contrast algorithm that
        affects midtones more than shadows/highlights. The adjustment is subtle.
        """
        if contrast == 0.0:
            return img
        
        contrast_norm = contrast / 100.0
        
        # Lightroom 2012 contrast: uses a gentle S-curve
        # The effect is more subtle than traditional contrast
        # Apply per channel
        result = img.copy()
        
        for c in range(3):
            channel = img[:, :, c]
            
            # Center around 0.5
            centered = channel - 0.5
            
            # Apply gentle S-curve: affects midtones more
            # Use a softer curve that doesn't crush shadows/highlights
            # For negative contrast (like -3), we want to reduce contrast slightly
            if contrast_norm > 0:
                # Positive contrast: gentle steepening
                factor = 1.0 + contrast_norm * 0.15  # More subtle
                result[:, :, c] = np.clip(0.5 + centered * factor, 0, 1)
            else:
                # Negative contrast: gentle flattening
                # This should reduce contrast without brightening overall
                factor = 1.0 + contrast_norm * 0.15  # More subtle
                result[:, :, c] = np.clip(0.5 + centered * factor, 0, 1)
        
        return result
    
    def _apply_highlights(self, img: np.ndarray, highlights: float) -> np.ndarray:
        """Apply highlights adjustment (-100 to +100)
        
        Lightroom 2012 highlights: affects brighter areas more, with smooth falloff.
        Negative values darken highlights, positive values brighten them.
        Should ONLY affect very bright areas (specular highlights), not skin tones.
        """
        if highlights == 0.0:
            return img
        
        highlights_norm = highlights / 100.0
        
        # Create a mask that emphasizes only very bright areas
        # Use per-channel approach for more accurate masking
        result = img.copy()
        
        for c in range(3):
            channel = img[:, :, c]
            
            # Create highlight mask: only affects very bright areas (above ~0.85)
            # This ensures skin tones (typically 0.4-0.7) are NOT affected
            # Use a very steep curve that only affects specular highlights
            highlight_curve = np.power(np.clip((channel - 0.85) / 0.15, 0, 1), 5.0)  # Extremely selective
            
            # Apply adjustment: negative values darken highlights
            # Scale down significantly to preserve contrast and details
            adjustment = highlights_norm * 0.1 * highlight_curve
            
            # Apply the adjustment
            result[:, :, c] = np.clip(channel + adjustment, 0, 1)
        
        return result
    
    def _apply_shadows(self, img: np.ndarray, shadows: float) -> np.ndarray:
        """Apply shadows adjustment (-100 to +100)
        
        Lightroom 2012 shadows: uses a tone curve that affects darker tones.
        The adjustment is subtle and preserves detail. Should affect mid-dark areas,
        not the very darkest (which are handled by blacks).
        """
        if shadows == 0.0:
            return img
        
        shadows_norm = shadows / 100.0
        
        # Lightroom 2012 shadows affects mid-dark to dark areas
        # Not the very darkest (that's blacks), but darker midtones
        result = img.copy()
        
        for c in range(3):
            channel = img[:, :, c]
            
            # Create shadow curve: affects darker midtones more than very dark areas
            # Peak around 0.2-0.4, fall off at both ends
            # This way it affects the background more than the very darkest shadows
            shadow_curve = np.power(np.clip(1.0 - channel * 2.5, 0, 1), 1.8)  # Affects mid-dark areas
            
            # Reduce effect on very dark areas (let blacks handle those)
            very_dark_mask = channel < 0.15
            shadow_curve[very_dark_mask] = shadow_curve[very_dark_mask] * 0.3  # Reduce effect on very dark
            
            # Apply adjustment: negative values darken, positive values brighten
            # For negative shadows (like -10), we need to darken significantly
            # Remove the scaling factor - let the preset value control the strength
            adjustment = shadows_norm * shadow_curve  # Use full preset value
            
            # Apply the adjustment
            result[:, :, c] = np.clip(channel + adjustment, 0, 1)
        
        return result
    
    def _apply_whites(self, img: np.ndarray, whites: float) -> np.ndarray:
        """Apply whites adjustment (-100 to +100)
        
        Lightroom 2012 whites: adjusts the white point.
        Should ONLY affect the very brightest areas (specular highlights), not skin tones.
        """
        if whites == 0.0:
            return img
        
        whites_norm = whites / 100.0
        
        # Lightroom 2012 whites uses a white point adjustment
        # Only affects the very brightest tones (specular highlights)
        result = img.copy()
        
        for c in range(3):
            channel = img[:, :, c]
            
            # Create a mask that only affects very bright areas (above ~0.9)
            # This ensures skin tones are NOT affected
            white_curve = np.power(np.clip((channel - 0.9) / 0.1, 0, 1), 6.0)  # Extremely selective
            
            # Apply adjustment: negative values reduce whites
            # Scale down significantly to preserve contrast and details
            adjustment = whites_norm * 0.08 * white_curve
            
            # Apply the adjustment
            result[:, :, c] = np.clip(channel + adjustment, 0, 1)
        
        return result
    
    def _apply_blacks(self, img: np.ndarray, blacks: float) -> np.ndarray:
        """Apply blacks adjustment (-100 to +100)
        
        Lightroom 2012 blacks: adjusts the black point using a curve.
        Negative values push more pixels towards black, positive values lift blacks.
        The effect is subtle and only affects the very darkest areas.
        """
        if blacks == 0.0:
            return img
        
        blacks_norm = blacks / 100.0
        
        # Lightroom 2012 blacks uses a subtle black point adjustment
        # Only affects the very darkest tones, preserving detail
        
        result = img.copy()
        
        for c in range(3):
            channel = img[:, :, c]
            
            # Create a curve that affects only the very darkest areas
            # Use a very steep curve that only affects pixels near black
            # The curve should peak at 0 and fall off very quickly
            black_curve = np.power(np.clip(1.0 - channel * 4.0, 0, 1), 4.0)  # Steeper falloff
            
            # Apply adjustment: negative values darken blacks
            # For negative blacks (like -30), we need to darken significantly
            # Remove excessive scaling - let the preset value control the strength
            # But still scale down a bit since blacks affects very dark areas
            adjustment = blacks_norm * 0.4 * black_curve  # Allow stronger darkening
            
            # Apply the adjustment
            result[:, :, c] = np.clip(channel + adjustment, 0, 1)
        
        return result
    
    def _apply_clarity(self, img: np.ndarray, clarity: float) -> np.ndarray:
        """Apply clarity adjustment (local contrast enhancement)"""
        if clarity == 0.0:
            return img
        
        clarity_norm = clarity / 100.0
        
        # TEMPORARILY SIMPLIFIED - The nested loop version might be causing issues
        # Use a simpler approach: apply slight sharpening
        # Simple unsharp mask approximation using convolution
        try:
            from scipy import ndimage
            # Apply Gaussian blur
            blurred = np.zeros_like(img)
            for c in range(3):
                blurred[:, :, c] = ndimage.gaussian_filter(img[:, :, c], sigma=1.0)
            
            # Create unsharp mask (detail layer)
            detail = img - blurred
            
            # Enhance detail proportionally
            enhanced = img + detail * clarity_norm
            return np.clip(enhanced, 0, 1)
        except ImportError:
            # Fallback: simple contrast boost (no blur)
            # Just apply a slight contrast adjustment
            enhanced = img * (1.0 + clarity_norm * 0.1)
            return np.clip(enhanced, 0, 1)
    
    def _apply_vibrance(self, img: np.ndarray, vibrance: float) -> np.ndarray:
        """Apply vibrance adjustment (selective saturation)"""
        vibrance_norm = vibrance / 100.0
        
        # TEMPORARILY DISABLED - HSV conversion might be causing issues
        # Use simpler RGB-based approach
        if vibrance_norm == 0.0:
            return img
        
        # Simple vibrance: boost less saturated pixels more
        # Calculate saturation as distance from gray
        gray = np.mean(img, axis=2, keepdims=True)
        saturation = np.abs(img - gray)
        avg_saturation = np.mean(saturation, axis=2, keepdims=True)
        
        # Apply vibrance (less saturated areas get more boost)
        boost = 1.0 + vibrance_norm * (1.0 - avg_saturation)
        result = gray + (img - gray) * boost
        return np.clip(result, 0, 1)
    
    def _apply_saturation(self, img: np.ndarray, saturation: float) -> np.ndarray:
        """Apply saturation adjustment"""
        saturation_norm = saturation / 100.0
        
        if saturation_norm == 0.0:
            return img
        
        # Simple saturation: blend with grayscale
        gray = np.mean(img, axis=2, keepdims=True)
        result = gray + (img - gray) * (1.0 + saturation_norm)
        return np.clip(result, 0, 1)
    
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
        
        # Avoid division by zero by adding small epsilon to delta
        delta_safe = np.where(delta == 0, 1, delta)
        
        # Hue calculation - handle delta == 0 case
        hue = np.zeros_like(max_val)
        
        # When delta != 0, calculate hue based on which channel is max
        delta_mask = delta != 0
        if np.any(delta_mask):
            # Red is max
            red_max_mask = delta_mask & (max_val == rgb[:, :, 0])
            if np.any(red_max_mask):
                hue[red_max_mask] = ((rgb[:, :, 1][red_max_mask] - rgb[:, :, 2][red_max_mask]) / delta_safe[red_max_mask]) % 6
            
            # Green is max
            green_max_mask = delta_mask & (max_val == rgb[:, :, 1])
            if np.any(green_max_mask):
                hue[green_max_mask] = 2 + (rgb[:, :, 2][green_max_mask] - rgb[:, :, 0][green_max_mask]) / delta_safe[green_max_mask]
            
            # Blue is max
            blue_max_mask = delta_mask & (max_val == rgb[:, :, 2])
            if np.any(blue_max_mask):
                hue[blue_max_mask] = 4 + (rgb[:, :, 0][blue_max_mask] - rgb[:, :, 1][blue_max_mask]) / delta_safe[blue_max_mask]
            
            # Normalize hue to [0, 1]
            hue[delta_mask] = hue[delta_mask] / 6
        
        hsv[:, :, 0] = hue
        
        # Saturation - avoid division by zero
        saturation = np.zeros_like(max_val)
        max_val_safe = np.where(max_val == 0, 1, max_val)  # Avoid division by zero
        saturation = delta / max_val_safe
        saturation = np.where(max_val == 0, 0, saturation)  # Set to 0 where max_val is 0
        hsv[:, :, 1] = saturation
        
        # Value
        hsv[:, :, 2] = max_val
        
        return hsv
    
    def _hsv_to_rgb(self, hsv: np.ndarray) -> np.ndarray:
        """Convert HSV to RGB"""
        # Ensure input is valid
        hsv = np.clip(hsv, 0, 1)
        
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
    
    def _apply_tone_curve(self, img: np.ndarray, tone_curve: list) -> np.ndarray:
        """Apply tone curve to image
        
        Args:
            img: Image array (0-1 range)
            tone_curve: List of (x, y) coordinate pairs defining the curve
            
        Returns:
            Image array with tone curve applied
        """
        if not tone_curve or len(tone_curve) < 2:
            return img
        
        # Convert tone curve points to numpy arrays
        # Tone curves in Lightroom are typically in 0-255 range
        x_coords = np.array([p[0] for p in tone_curve])
        y_coords = np.array([p[1] for p in tone_curve])
        
        # Normalize to 0-1 range if needed
        if x_coords.max() > 1.0 or y_coords.max() > 1.0:
            x_coords = x_coords / 255.0
            y_coords = y_coords / 255.0
        
        # Create interpolation function
        # Use linear interpolation between curve points
        # For values outside the curve range, use nearest point
        try:
            from scipy.interpolate import interp1d
        except ImportError:
            # Fallback to numpy-based interpolation if scipy not available
            logger.warning("scipy not available, using simple tone curve interpolation")
            return self._apply_tone_curve_simple(img, tone_curve)
        
        # Ensure curve is monotonic for interpolation
        # Sort by x coordinate
        sort_idx = np.argsort(x_coords)
        x_coords = x_coords[sort_idx]
        y_coords = y_coords[sort_idx]
        
        # Create interpolation function
        # Use 'linear' interpolation, with 'nearest' for extrapolation
        try:
            interp_func = interp1d(
                x_coords, y_coords,
                kind='linear',
                bounds_error=False,
                fill_value=(y_coords[0], y_coords[-1])
            )
        except:
            # Fallback to simple linear interpolation
            return img
        
        # Apply tone curve to each channel
        result = np.zeros_like(img)
        for c in range(img.shape[2]):
            channel = img[:, :, c]
            # Apply curve
            result[:, :, c] = np.clip(interp_func(channel), 0, 1)
        
        return result
    
    def _apply_channel_tone_curves(
        self, img: np.ndarray,
        curve_red: Optional[list],
        curve_green: Optional[list],
        curve_blue: Optional[list]
    ) -> np.ndarray:
        """Apply per-channel tone curves to image
        
        Args:
            img: Image array (0-1 range)
            curve_red: Red channel tone curve (list of (x, y) pairs)
            curve_green: Green channel tone curve
            curve_blue: Blue channel tone curve
            
        Returns:
            Image array with channel tone curves applied
        """
        result = img.copy()
        
        # Apply each channel curve independently
        if curve_red:
            red_channel = img[:, :, 0:1]
            result[:, :, 0] = self._apply_tone_curve(red_channel, curve_red)[:, :, 0]
        if curve_green:
            green_channel = img[:, :, 1:2]
            result[:, :, 1] = self._apply_tone_curve(green_channel, curve_green)[:, :, 0]
        if curve_blue:
            blue_channel = img[:, :, 2:3]
            result[:, :, 2] = self._apply_tone_curve(blue_channel, curve_blue)[:, :, 0]
        
        return result
    
    def _apply_tone_curve_simple(self, img: np.ndarray, tone_curve: list) -> np.ndarray:
        """Simple tone curve application without scipy (fallback)"""
        if not tone_curve or len(tone_curve) < 2:
            return img
        
        # Convert to numpy arrays and normalize
        x_coords = np.array([p[0] for p in tone_curve])
        y_coords = np.array([p[1] for p in tone_curve])
        
        if x_coords.max() > 1.0 or y_coords.max() > 1.0:
            x_coords = x_coords / 255.0
            y_coords = y_coords / 255.0
        
        # Sort by x
        sort_idx = np.argsort(x_coords)
        x_coords = x_coords[sort_idx]
        y_coords = y_coords[sort_idx]
        
        # Simple linear interpolation using numpy
        result = np.zeros_like(img)
        for c in range(img.shape[2]):
            channel = img[:, :, c]
            # Find which segment each pixel value falls into
            # Use searchsorted to find insertion points
            indices = np.searchsorted(x_coords, channel, side='right')
            indices = np.clip(indices, 1, len(x_coords) - 1)
            
            # Linear interpolation
            x0 = x_coords[indices - 1]
            x1 = x_coords[indices]
            y0 = y_coords[indices - 1]
            y1 = y_coords[indices]
            
            # Avoid division by zero
            dx = x1 - x0
            dx = np.where(dx == 0, 1, dx)
            
            # Interpolate
            t = (channel - x0) / dx
            result[:, :, c] = np.clip(y0 + t * (y1 - y0), 0, 1)
        
        return result
    
    def _apply_texture(self, img: np.ndarray, texture: float) -> np.ndarray:
        """Apply texture adjustment (similar to clarity but preserves edges better)"""
        # Texture is similar to clarity but uses a different algorithm
        # For now, use a simplified version
        if texture == 0.0:
            return img
        
        # Convert to grayscale for edge detection
        gray = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
        
        # Simple high-pass filter (edge detection)
        kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]]) / 8.0
        try:
            from scipy import ndimage
            edges = ndimage.convolve(gray, kernel)
        except ImportError:
            # Fallback: simple edge detection using differences
            edges = np.abs(gray - np.roll(gray, 1, axis=0)) + np.abs(gray - np.roll(gray, 1, axis=1))
            edges = edges / 2.0
        
        # Apply texture adjustment
        texture_factor = texture / 100.0
        for c in range(3):
            img[:, :, c] = np.clip(img[:, :, c] + edges * texture_factor * 0.1, 0, 1)
        
        return img
    
    def _apply_dehaze(self, img: np.ndarray, dehaze: float) -> np.ndarray:
        """Apply dehaze adjustment"""
        if dehaze == 0.0:
            return img
        
        # Dehaze works by increasing contrast in areas with low saturation
        hsv = self._rgb_to_hsv(img)
        saturation = hsv[:, :, 1]
        
        # Create mask for low saturation areas (hazy areas)
        haze_mask = 1.0 - saturation
        
        # Apply dehaze (positive values reduce haze, negative increase it)
        dehaze_factor = dehaze / 100.0
        
        # Increase contrast in hazy areas
        for c in range(3):
            channel = img[:, :, c]
            # Apply contrast adjustment weighted by haze mask
            contrast_adjustment = (channel - 0.5) * dehaze_factor * haze_mask
            img[:, :, c] = np.clip(channel + contrast_adjustment, 0, 1)
        
        return img
    
    def _apply_hsl_adjustments(self, img: np.ndarray) -> np.ndarray:
        """Apply HSL adjustments per color range"""
        # Convert to HSV for easier manipulation
        hsv = self._rgb_to_hsv(img)
        h = hsv[:, :, 0] * 360.0  # Convert to degrees
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]
        
        # Define color ranges (in degrees)
        color_ranges = {
            'Red': (0, 15, 345, 360),
            'Orange': (15, 45),
            'Yellow': (45, 75),
            'Green': (75, 165),
            'Aqua': (165, 195),
            'Blue': (195, 255),
            'Purple': (255, 285),
            'Magenta': (285, 345),
        }
        
        # Apply hue adjustments
        for color, ranges in color_ranges.items():
            hue_adj = self.adjustments.get(f'HueAdjustment{color}', 0.0)
            if hue_adj != 0.0:
                if len(ranges) == 4:  # Red wraps around
                    mask = ((h >= ranges[0]) & (h <= ranges[1])) | ((h >= ranges[2]) & (h <= ranges[3]))
                else:
                    mask = (h >= ranges[0]) & (h < ranges[1])
                h[mask] = (h[mask] + hue_adj) % 360.0
        
        # Apply saturation adjustments
        for color, ranges in color_ranges.items():
            sat_adj = self.adjustments.get(f'SaturationAdjustment{color}', 0.0)
            if sat_adj != 0.0:
                if len(ranges) == 4:
                    mask = ((h >= ranges[0]) & (h <= ranges[1])) | ((h >= ranges[2]) & (h <= ranges[3]))
                else:
                    mask = (h >= ranges[0]) & (h < ranges[1])
                s[mask] = np.clip(s[mask] + sat_adj / 100.0, 0, 1)
        
        # Apply luminance adjustments
        for color, ranges in color_ranges.items():
            lum_adj = self.adjustments.get(f'LuminanceAdjustment{color}', 0.0)
            if lum_adj != 0.0:
                if len(ranges) == 4:
                    mask = ((h >= ranges[0]) & (h <= ranges[1])) | ((h >= ranges[2]) & (h <= ranges[3]))
                else:
                    mask = (h >= ranges[0]) & (h < ranges[1])
                v[mask] = np.clip(v[mask] + lum_adj / 100.0, 0, 1)
        
        # Convert back to RGB
        hsv[:, :, 0] = h / 360.0
        hsv[:, :, 1] = s
        hsv[:, :, 2] = v
        return self._hsv_to_rgb(hsv)
    
    def _apply_split_toning(self, img: np.ndarray, shadow_hue: Optional[float], 
                           shadow_sat: float, highlight_hue: Optional[float],
                           highlight_sat: float, balance: float) -> np.ndarray:
        """Apply split toning (color cast to shadows and highlights)
        
        Split toning in Lightroom works by:
        1. Converting image to grayscale (luminance)
        2. Creating masks for shadows and highlights based on luminance
        3. Blending the tint color into those areas
        """
        if (shadow_hue is None or shadow_sat == 0) and (highlight_hue is None or highlight_sat == 0):
            return img
        
        # Convert to grayscale for luminance-based masking
        luminance = 0.299 * img[:, :, 0] + 0.587 * img[:, :, 1] + 0.114 * img[:, :, 2]
        
        # Balance affects the transition point: -100 = all shadows, +100 = all highlights, 0 = balanced
        balance_factor = balance / 100.0
        transition = 0.5 + balance_factor * 0.3  # Adjust transition point
        
        # Create masks for shadows and highlights
        # Shadows: darker areas
        shadow_mask = np.clip(1.0 - (luminance / transition), 0, 1)
        shadow_mask = np.power(shadow_mask, 2.0)  # Smooth falloff
        
        # Highlights: brighter areas  
        highlight_mask = np.clip((luminance - transition) / (1.0 - transition), 0, 1)
        highlight_mask = np.power(highlight_mask, 2.0)  # Smooth falloff
        
        # Normalize masks so they don't overlap too much
        total_mask = shadow_mask + highlight_mask
        total_mask = np.where(total_mask > 1.0, total_mask, 1.0)
        shadow_mask = shadow_mask / total_mask
        highlight_mask = highlight_mask / total_mask
        
        result = img.copy()
        
        # Apply shadow toning
        if shadow_hue is not None and shadow_sat > 0:
            # Convert hue to RGB color (saturated color at that hue)
            shadow_hue_norm = shadow_hue / 360.0
            shadow_hsv = np.array([[[shadow_hue_norm, 1.0, 1.0]]])
            shadow_rgb = self._hsv_to_rgb(shadow_hsv)[0, 0, :]
            
            # Blend the tint color into shadows
            shadow_strength = shadow_sat / 100.0
            for c in range(3):
                # Mix original color with tint color based on mask and strength
                tinted = result[:, :, c] * (1.0 - shadow_strength) + shadow_rgb[c] * shadow_strength
                result[:, :, c] = result[:, :, c] * (1.0 - shadow_mask) + tinted * shadow_mask
        
        # Apply highlight toning
        if highlight_hue is not None and highlight_sat > 0:
            # Convert hue to RGB color (saturated color at that hue)
            highlight_hue_norm = highlight_hue / 360.0
            highlight_hsv = np.array([[[highlight_hue_norm, 1.0, 1.0]]])
            highlight_rgb = self._hsv_to_rgb(highlight_hsv)[0, 0, :]
            
            # Blend the tint color into highlights
            highlight_strength = highlight_sat / 100.0
            for c in range(3):
                # Mix original color with tint color based on mask and strength
                tinted = result[:, :, c] * (1.0 - highlight_strength) + highlight_rgb[c] * highlight_strength
                result[:, :, c] = result[:, :, c] * (1.0 - highlight_mask) + tinted * highlight_mask
        
        return np.clip(result, 0, 1)
    
    def _apply_color_grading(self, img: np.ndarray, midtone_hue: Optional[float], midtone_sat: float,
                            shadow_lum: float, midtone_lum: float, highlight_lum: float,
                            blending: float) -> np.ndarray:
        """Apply color grading (this creates the yellow tone!)
        
        Color grading in Lightroom works by:
        1. Creating masks for shadows, midtones, and highlights based on luminance
        2. Adjusting luminance in each region
        3. Shifting hue and adjusting saturation in midtones (and optionally shadows/highlights)
        
        This version uses RGB-based color mixing to avoid HSV conversion issues.
        """
        if midtone_hue is None and shadow_lum == 0.0 and midtone_lum == 0.0 and highlight_lum == 0.0:
            return img
        
        # Calculate luminance for masking (using Rec. 709 weights)
        luminance = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
        
        # Create masks for shadows, midtones, and highlights
        # Blending parameter affects how sharp the transitions are (0-100, default 50)
        blend_factor = blending / 100.0
        transition_sharpness = 0.3 + blend_factor * 0.4  # 0.3 to 0.7
        
        # Shadow mask: darker areas (luminance < 0.35) - adjusted to exclude very dark backgrounds
        shadow_mask = np.clip(1.0 - (luminance / 0.35), 0, 1)
        shadow_mask = np.power(shadow_mask, 2.0 / transition_sharpness)
        
        # Highlight mask: brighter areas (luminance > 0.65)
        highlight_mask = np.clip((luminance - 0.65) / 0.35, 0, 1)
        highlight_mask = np.power(highlight_mask, 2.0 / transition_sharpness)
        
        # Midtone mask: everything else (0.35 to 0.65 range)
        # This ensures color grading primarily affects the subject, not very dark backgrounds
        midtone_mask = 1.0 - shadow_mask - highlight_mask
        midtone_mask = np.clip(midtone_mask, 0, 1)
        
        # Further refine midtone mask to exclude very dark areas (background)
        # This prevents color grading from affecting dark backgrounds
        midtone_mask = midtone_mask * np.clip(luminance * 2.0, 0, 1)
        
        # Normalize masks to ensure they sum to 1
        total_mask = shadow_mask + midtone_mask + highlight_mask
        total_mask = np.where(total_mask > 0, total_mask, 1.0)
        shadow_mask = shadow_mask / total_mask
        midtone_mask = midtone_mask / total_mask
        highlight_mask = highlight_mask / total_mask
        
        result = img.copy()
        
        # Apply luminance adjustments to each region
        # Heavily scale down to prevent over-brightening and preserve details
        # Lightroom's color grading luminance is very subtle
        if shadow_lum != 0.0:
            lum_factor = shadow_lum / 100.0 * 0.15  # Heavily scaled down
            for c in range(3):
                result[:, :, c] = result[:, :, c] + lum_factor * shadow_mask
        
        if midtone_lum != 0.0:
            # Midtone luminance should be extremely subtle to avoid over-brightening skin
            lum_factor = midtone_lum / 100.0 * 0.05  # Very minimal effect
            for c in range(3):
                result[:, :, c] = result[:, :, c] + lum_factor * midtone_mask
        
        if highlight_lum != 0.0:
            lum_factor = highlight_lum / 100.0 * 0.15  # Heavily scaled down
            for c in range(3):
                result[:, :, c] = result[:, :, c] + lum_factor * highlight_mask
        
        # Apply hue shift and saturation in midtones (THIS IS THE YELLOW TONE!)
        # Using RGB-based approach to avoid HSV conversion issues
        if midtone_hue is not None and (midtone_hue != 0.0 or midtone_sat != 0.0):
            # Convert hue to RGB color (yellow is around hue 60 degrees)
            # Lightroom's color grading wheel: 0=red, 60=yellow, 120=green, 180=cyan, 240=blue, 300=magenta
            hue_degrees = midtone_hue % 360.0
            hue_normalized = hue_degrees / 360.0
            
            # Convert hue to RGB using HSV conversion for a single color
            # Create a fully saturated color at this hue
            hsv_color = np.array([[[hue_normalized, 1.0, 1.0]]], dtype=np.float32)
            target_rgb = self._hsv_to_rgb(hsv_color)[0, 0, :]  # Shape: (3,)
            
            # Apply color shift: blend original color towards target color in midtones
            # The saturation parameter controls how much to blend
            # Reduce blend strength to prevent over-brightening and preserve details
            blend_strength = abs(midtone_sat) / 100.0 if midtone_sat != 0.0 else 0.1
            blend_strength = blend_strength * 0.5  # Reduce by 50% to prevent over-brightening
            
            # Blend towards target color only in midtones
            for c in range(3):
                # Mix original with target color based on mask and strength
                blended = result[:, :, c] * (1.0 - blend_strength * midtone_mask) + target_rgb[c] * blend_strength * midtone_mask
                result[:, :, c] = blended
        
        return np.clip(result, 0, 1)
    
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

