"""
CamScanner-like Document Processing API

Simple, automatic document scanning with support for:
- Single flat documents (receipts, papers, ID cards)
- Book spreads with center fold
- Partial books with lateral fold

Usage:
    from camscanner import CamScanner

    scanner = CamScanner()
    result = scanner.scan("document.jpg")

    if result.success:
        result.save("output.jpg")

Features:
    - Automatic document type detection
    - Edge detection and perspective correction
    - Smart background cropping
    - Fold detection and page splitting
    - Graceful fallback on detection failure
    - Quality scoring and warnings
"""

from .scanner import CamScanner, ScanResult

__version__ = "1.0.0"
__all__ = ["CamScanner", "ScanResult"]
