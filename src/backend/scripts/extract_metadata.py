#!/usr/bin/env python3
import sys
import json
import xml.etree.ElementTree as ET

def get_value(root, xpath, namespaces):
    """Extract value from XML using XPath."""
    # Handle attribute syntax (@attr)
    if '@' in xpath:
        parts = xpath.rsplit('/', 1)
        if len(parts) == 2:
            element_path, attr_part = parts
            attr_name = attr_part.replace('@', '')

            # Handle namespaced attributes (e.g., @xlink:href)
            elem = root.find(element_path, namespaces)
            if elem is not None:
                # Try with namespace
                for ns_prefix, ns_uri in namespaces.items():
                    full_attr = f'{{{ns_uri}}}{attr_name.split(":")[-1]}'
                    if full_attr in elem.attrib:
                        return elem.attrib[full_attr]
                # Try without namespace
                if attr_name in elem.attrib:
                    return elem.attrib[attr_name]
                # Try with colon (xlink:href)
                if ':' in attr_name and attr_name in elem.attrib:
                    return elem.attrib[attr_name]
        return None

    # Regular element
    elem = root.find(xpath, namespaces)
    if elem is not None:
        if elem.text:
            return elem.text.strip()
    return None

def extract_metadata(xml_path, json_path, map_path, quality='all'):
    """Extract metadata from XML to JSON using mapping."""

    # Parse XML
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Namespaces
    ns = {
        'md': 'http://www.iccu.sbn.it/metaAG1.pdf',  # default namespace
        'dc': 'http://purl.org/dc/elements/1.1/',
        'niso': 'http://www.niso.org/pdfs/DataDict.pdf',
        'xlink': 'http://www.w3.org/1999/xlink'
    }

    # Load mapping
    with open(map_path, 'r') as f:
        mapping = json.load(f)

    # Extract document metadata
    doc_meta = {}
    for key, xpath in mapping['document'].items():
        if isinstance(xpath, bool):
            doc_meta[key] = xpath
        elif isinstance(xpath, str):
            val = get_value(root, xpath, ns)
            doc_meta[key] = val if val else None

    # Extract images metadata
    images = []
    for img_elem in root.findall('.//md:img', ns):
        # Collect all file hrefs (main + altimg)
        all_files = []

        # Main file
        main_file = img_elem.find('md:file', ns)
        if main_file is not None:
            href = main_file.get('{http://www.w3.org/1999/xlink}href')
            if href:
                all_files.append(href)

        # Altimg files
        for altimg in img_elem.findall('md:altimg', ns):
            alt_file = altimg.find('md:file', ns)
            if alt_file is not None:
                href = alt_file.get('{http://www.w3.org/1999/xlink}href')
                if href:
                    all_files.append(href)

        # Filter by quality
        selected_file = None
        if quality == 'all':
            selected_file = all_files[0] if all_files else None
        else:
            for f in all_files:
                if f'/{quality}/' in f.lower():
                    selected_file = f
                    break

        # Skip if no matching file found
        if not selected_file:
            continue

        img_meta = {}

        # Override filename with selected file (basename only)
        import os
        img_meta['filename'] = os.path.basename(selected_file)

        for key, xpath in mapping['image'].items():
            if key == 'filename':
                continue  # Already set above

            if isinstance(xpath, dict):
                # Nested object
                nested = {}
                for nkey, nxpath in xpath.items():
                    # Remove 'img/' prefix but keep namespace prefixes
                    clean_xpath = nxpath.replace('img/', '')
                    val = get_value(img_elem, clean_xpath, ns)
                    nested[nkey] = val if val else None
                img_meta[key] = nested
            else:
                # Remove 'img/' prefix but keep namespace prefixes
                clean_xpath = xpath.replace('img/', '')
                val = get_value(img_elem, clean_xpath, ns)
                img_meta[key] = val if val else None

        images.append(img_meta)

    # Output JSON
    result = {
        'document': doc_meta,
        'images': images
    }

    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: extract_metadata.py <xml_file> <output_json> <map_file> [quality]")
        sys.exit(1)

    quality = sys.argv[4] if len(sys.argv) > 4 else 'all'
    extract_metadata(sys.argv[1], sys.argv[2], sys.argv[3], quality)
