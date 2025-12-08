"""
XMP Preset Parser for Lightroom Presets
Parses .xmp preset files to extract Lightroom adjustment parameters
"""

import xml.etree.ElementTree as ET
import re
from typing import Dict, Optional, Any
from pathlib import Path


class XMPPresetParser:
    """Parse Lightroom XMP preset files and extract adjustment parameters"""
    
    def __init__(self, preset_path: str):
        self.preset_path = Path(preset_path)
        if not self.preset_path.exists():
            raise FileNotFoundError(f"Preset file not found: {preset_path}")
        
        self.adjustments = {}
        self._parse()
    
    def _parse(self):
        """Parse the XMP preset file"""
        try:
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
        
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XMP file: {e}")
        except Exception as e:
            raise ValueError(f"Error reading preset file: {e}")
    
    def _extract_crs_settings(self, desc, namespaces):
        """Extract Camera Raw Settings from XMP"""
        crs_prefix = '{http://ns.adobe.com/camera-raw-settings/1.0/}'
        
        # Common Camera Raw adjustments
        crs_params = [
            'Exposure', 'Contrast', 'Highlights', 'Shadows', 'Whites', 'Blacks',
            'Clarity', 'Vibrance', 'Saturation', 'Temperature', 'Tint',
            'Sharpness', 'LuminanceSmoothing', 'ColorNoiseReduction',
            'GrainAmount', 'GrainSize', 'GrainRoughness',
            'LensProfileEnable', 'LensManualDistortionAmount',
            'VignetteAmount', 'DefringePurpleAmount', 'DefringeGreenAmount',
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
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type"""
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

