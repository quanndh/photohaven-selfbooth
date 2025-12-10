"""
XMP Preset Parser for Lightroom Presets
Parses .xmp preset files to extract Lightroom adjustment parameters
Supports both plain .xmp files and encrypted .encrypted files
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, Optional, Any
from pathlib import Path
import io


class XMPPresetParser:
    """Parse Lightroom XMP preset files and extract adjustment parameters"""
    
    def __init__(self, preset_path: str, encrypted: bool = False):
        """
        Initialize preset parser
        
        Args:
            preset_path: Path to preset file (.xmp or .encrypted)
            encrypted: If True, treat as encrypted file (requires preset_encryption module)
        """
        self.preset_path = Path(preset_path)
        if not self.preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        
        self.encrypted = encrypted or (self.preset_path.suffix == '.encrypted')
        self.adjustments = {}
        self._parse()
    
    def _parse(self):
        """Parse the XMP preset file"""
        try:
            # Handle encrypted presets
            if self.encrypted:
                try:
                    from preset_encryption import PresetEncryption
                    encryption = PresetEncryption()
                    preset_data = encryption.decrypt_to_memory(str(self.preset_path))
                    tree = ET.parse(io.BytesIO(preset_data))
                except ImportError:
                    raise ImportError("preset_encryption module required for encrypted presets. Install cryptography: pip install cryptography")
                except Exception as e:
                    raise ValueError(f"Failed to decrypt preset: {e}")
            else:
                tree = ET.parse(self.preset_path)
            
            root = tree.getroot()
            
            # Lightroom stores adjustments in rdf:Description elements
            # with various namespaces
            namespaces = {
                'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
                'xmp': 'http://ns.adobe.com/xap/1.0/',
                'xmpMM': 'http://ns.adobe.com/xap/1.0/mm/',
                'lr': 'http://ns.adobe.com/lightroom/1.0/',
                'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/',
                'x': 'adobe:ns:meta/',
            }
            
            # Find all rdf:Description elements
            descriptions = root.findall('.//rdf:Description', namespaces)
            
            for desc in descriptions:
                # Extract Camera Raw Settings (crs namespace)
                self._extract_crs_settings(desc, namespaces)
                
                # Extract Lightroom-specific settings (lr namespace)
                self._extract_lr_settings(desc, namespaces)
                
                # Extract tone curves from rdf:Seq elements (ToneCurvePV2012)
                self._extract_tone_curves(desc, namespaces)
        
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XMP file: {e}")
        except Exception as e:
            raise ValueError(f"Error reading preset file: {e}")
    
    def _extract_crs_settings(self, desc, namespaces):
        """Extract Camera Raw Settings from XMP"""
        crs_prefix = '{http://ns.adobe.com/camera-raw-settings/1.0/}'
        
        # Common Camera Raw adjustments
        crs_params = [
            'Exposure', 'Exposure2012', 'Contrast', 'Contrast2012', 
            'Highlights', 'Highlights2012', 'Shadows', 'Shadows2012', 
            'Whites', 'Whites2012', 'Blacks', 'Blacks2012',
            'Clarity', 'Clarity2012', 'Vibrance', 'Saturation', 
            'Temperature', 'Tint', 'Texture', 'Dehaze',
            'Sharpness', 'LuminanceSmoothing', 'ColorNoiseReduction',
            'GrainAmount', 'GrainSize', 'GrainRoughness',
            'LensProfileEnable', 'LensManualDistortionAmount',
            'VignetteAmount', 'PostCropVignetteAmount', 'DefringePurpleAmount', 'DefringeGreenAmount',
            'ChromaticAberrationB', 'ChromaticAberrationR',
            'ToneCurveName', 'ToneCurve', 'ToneCurveRed', 'ToneCurveGreen', 'ToneCurveBlue',
            'HueAdjustmentRed', 'HueAdjustmentOrange', 'HueAdjustmentYellow',
            'HueAdjustmentGreen', 'HueAdjustmentAqua', 'HueAdjustmentBlue',
            'HueAdjustmentPurple', 'HueAdjustmentMagenta',
            'SaturationAdjustmentRed', 'SaturationAdjustmentOrange', 'SaturationAdjustmentYellow',
            'SaturationAdjustmentGreen', 'SaturationAdjustmentAqua', 'SaturationAdjustmentBlue',
            'SaturationAdjustmentPurple', 'SaturationAdjustmentMagenta',
            'LuminanceAdjustmentRed', 'LuminanceAdjustmentOrange', 'LuminanceAdjustmentYellow',
            'LuminanceAdjustmentGreen', 'LuminanceAdjustmentAqua', 'LuminanceAdjustmentBlue',
            'LuminanceAdjustmentPurple', 'LuminanceAdjustmentMagenta',
            # Split Toning
            'SplitToningShadowHue', 'SplitToningShadowSaturation',
            'SplitToningHighlightHue', 'SplitToningHighlightSaturation', 'SplitToningBalance',
            # Color Grading
            'ColorGradeShadowLum', 'ColorGradeMidtoneLum', 'ColorGradeHighlightLum',
            'ColorGradeMidtoneHue', 'ColorGradeMidtoneSat',
            'ColorGradeGlobalHue', 'ColorGradeGlobalSat', 'ColorGradeGlobalLum',
            'ColorGradeBlending',
        ]
        
        for param in crs_params:
            attr_name = f'{crs_prefix}{param}'
            value = desc.get(attr_name)
            if value is not None:
                # Convert string values to appropriate types
                self.adjustments[param] = self._convert_value(value)
    
    def _extract_lr_settings(self, desc, namespaces):
        """Extract Lightroom-specific settings"""
        lr_prefix = '{http://ns.adobe.com/lightroom/1.0/}'
        
        # Lightroom-specific parameters
        lr_params = [
            'AutoTone', 'AutoLateralCA', 'AutoExposure', 'AutoContrast',
            'ProcessVersion', 'ConvertToGrayscale', 'GradientBasedCorrections',
            'CircularGradientBasedCorrections', 'PaintBasedCorrections',
        ]
        
        for param in lr_params:
            attr_name = f'{lr_prefix}{param}'
            value = desc.get(attr_name)
            if value is not None:
                self.adjustments[param] = self._convert_value(value)
    
    def _extract_tone_curves(self, desc, namespaces):
        """Extract tone curves from rdf:Seq elements (ToneCurvePV2012)"""
        crs_prefix = '{http://ns.adobe.com/camera-raw-settings/1.0/}'
        
        # Tone curve elements stored as sequences
        tone_curve_names = [
            'ToneCurvePV2012',
            'ToneCurvePV2012Red',
            'ToneCurvePV2012Green',
            'ToneCurvePV2012Blue',
        ]
        
        for curve_name in tone_curve_names:
            curve_elem = desc.find(f'.//{crs_prefix}{curve_name}', namespaces)
            if curve_elem is not None:
                seq = curve_elem.find('rdf:Seq', namespaces)
                if seq is not None:
                    coords = []
                    for li in seq.findall('rdf:li', namespaces):
                        text = li.text
                        if text and ',' in text:
                            try:
                                x, y = text.split(',')
                                coords.append((float(x.strip()), float(y.strip())))
                            except ValueError:
                                pass
                    if len(coords) > 0:
                        # Map to standard names
                        if curve_name == 'ToneCurvePV2012':
                            self.adjustments['ToneCurve'] = coords
                        elif curve_name == 'ToneCurvePV2012Red':
                            self.adjustments['ToneCurveRed'] = coords
                        elif curve_name == 'ToneCurvePV2012Green':
                            self.adjustments['ToneCurveGreen'] = coords
                        elif curve_name == 'ToneCurvePV2012Blue':
                            self.adjustments['ToneCurveBlue'] = coords
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type"""
        # Special handling for tone curves (comma-separated coordinate pairs)
        if 'ToneCurve' in str(value) or (',' in value and ' ' in value):
            # Check if it looks like a tone curve (coordinate pairs)
            try:
                parts = value.strip().split()
                if len(parts) > 0:
                    # Try to parse as coordinate pairs
                    coords = []
                    for part in parts:
                        if ',' in part:
                            x, y = part.split(',')
                            coords.append((float(x), float(y)))
                    if len(coords) > 0:
                        return coords  # Return as list of tuples
            except (ValueError, AttributeError):
                pass  # Not a tone curve, continue with normal parsing
        
        # Try boolean
        if value.lower() in ('true', '1', 'yes'):
            return True
        if value.lower() in ('false', '0', 'no'):
            return False
        
        # Try integer
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string if all else fails
        return value
    
    def get_adjustments(self) -> Dict[str, Any]:
        """Get all parsed adjustments"""
        return self.adjustments.copy()
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a specific adjustment value"""
        return self.adjustments.get(key, default)
    
    def has_adjustment(self, key: str) -> bool:
        """Check if a specific adjustment exists"""
        return key in self.adjustments

