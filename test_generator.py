#!/usr/bin/env python3
"""
Test Data Generator for Image Processing Leggio App

Generates a complete test dataset including:
- Folder structure with images (JPG, PNG, TIF)
- CSV file with metadata
- JSON mapping configuration

Usage:
    python test_generator.py --output test_data --documents 5 --images-per-doc 4
    python test_generator.py --output test_data --large
"""

import argparse
import csv
import json
import os
import random
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

# =======================
# CONFIGURATION
# =======================

CATEGORIES = ["Historical", "Modern", "Contemporary", "Medieval", "Renaissance", "Baroque"]
MATERIALS = ["Photo", "Drawing", "Manuscript", "Painting", "Document", "Book"]
PERIODS = ["Ancient", "Medieval", "Renaissance", "Modern", "Contemporary", "Victorian"]
SUBJECTS = [
    "Portrait", "Landscape", "Architecture", "Still Life", "Abstract",
    "Religious", "Historical Scene", "Nature", "Urban", "Interior"
]

AUTHORS = [
    "Giovanni Rossi", "Maria Bianchi", "Paolo Verdi", "Laura Neri",
    "Marco Colombo", "Anna Ricci", "Francesco Romano", "Sofia Greco"
]

DOCUMENT_TITLES_IT = [
    "Archivio Storico Comunale",
    "Collezione Fotografica Ottocentesca",
    "Manoscritti Medievali",
    "Dipinti Rinascimentali",
    "Documenti dell'Archivio di Stato",
    "Fotografie Storiche della Citta",
    "Raccolta di Disegni Antichi",
    "Codici Miniati",
    "Album Fotografico Familiare",
    "Carte Geografiche Storiche",
    "Stampe e Incisioni",
    "Libri Antichi Illustrati",
    "Documenti Notarili Storici",
    "Ritratti di Famiglia",
    "Vedute Paesaggistiche"
]

DOCUMENT_TITLES_EN = [
    "Municipal Historical Archive",
    "19th Century Photographic Collection",
    "Medieval Manuscripts",
    "Renaissance Paintings",
    "State Archive Documents",
    "Historical City Photographs",
    "Collection of Ancient Drawings",
    "Illuminated Codices",
    "Family Photo Album",
    "Historical Maps",
    "Prints and Engravings",
    "Illustrated Antique Books",
    "Historical Notarial Documents",
    "Family Portraits",
    "Landscape Views"
]

DOCUMENT_TITLES_DE = [
    "Stadtisches Historisches Archiv",
    "Fotografische Sammlung des 19. Jahrhunderts",
    "Mittelalterliche Manuskripte",
    "Renaissance Gemalde",
    "Staatsarchiv Dokumente",
    "Historische Stadtfotografien",
    "Sammlung Alter Zeichnungen",
    "Illuminierte Kodizes",
    "Familien Fotoalbum",
    "Historische Karten",
    "Drucke und Gravuren",
    "Illustrierte Antike Bucher",
    "Historische Notarielle Dokumente",
    "Familienportrats",
    "Landschaftsansichten"
]

ARCHIVES = [
    {
        "name": "Archivio di Stato",
        "path": "Archivio di Stato",
        "description_it": "Archivio di Stato - Descrizione IT",
        "description_en": "State Archive - Description EN",
        "description_de": "Staatsarchiv - Beschreibung DE",
        "children": [
            {
                "name": "Fondo Medievale",
                "path": "Archivio di Stato/Fondo Medievale",
                "description_it": "Fondo Medievale - Descrizione IT",
                "description_en": "Medieval Collection - Description EN",
                "description_de": "Mittelalterlicher Bestand - Beschreibung DE",
                "parent": "Archivio di Stato"
            },
            {
                "name": "Fondo Moderno",
                "path": "Archivio di Stato/Fondo Moderno",
                "description_it": "Fondo Moderno - Descrizione IT",
                "description_en": "Modern Collection - Description EN",
                "description_de": "Moderner Bestand - Beschreibung DE",
                "parent": "Archivio di Stato"
            }
        ]
    },
    {
        "name": "Archivio Fotografico",
        "path": "Archivio Fotografico",
        "description_it": "Archivio Fotografico - Descrizione IT",
        "description_en": "Photographic Archive - Description EN",
        "description_de": "Fotoarchiv - Beschreibung DE",
        "children": []
    }
]

# =======================
# IMAGE GENERATION
# =======================

def generate_random_image(width=800, height=600, image_format="JPEG"):
    """Generate a random colored image with text overlay."""
    # Random background color
    bg_color = (
        random.randint(100, 255),
        random.randint(100, 255),
        random.randint(100, 255)
    )

    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Draw random shapes
    for _ in range(random.randint(3, 8)):
        shape_type = random.choice(['rectangle', 'ellipse', 'line'])
        color = (
            random.randint(0, 200),
            random.randint(0, 200),
            random.randint(0, 200)
        )

        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)

        # Ensure correct coordinate order
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1

        if shape_type == 'rectangle':
            draw.rectangle([x1, y1, x2, y2], fill=color, outline=(0, 0, 0))
        elif shape_type == 'ellipse':
            draw.ellipse([x1, y1, x2, y2], fill=color, outline=(0, 0, 0))
        else:
            draw.line([x1, y1, x2, y2], fill=color, width=3)

    return img

def generate_book_page_image(width=1200, height=1600):
    """Generate an image that looks like a scanned book page (for testing crop.py)."""
    # White background
    img = Image.new('RGB', (width, height), color=(245, 245, 240))
    draw = ImageDraw.Draw(img)

    # Add some text-like lines
    margin_left = random.randint(80, 150)
    margin_right = width - random.randint(80, 150)
    margin_top = random.randint(100, 150)
    line_height = 25

    for i in range(40):
        y = margin_top + i * line_height
        if y > height - 150:
            break
        # Random line length (simulating text)
        line_end = random.randint(margin_left + 300, margin_right)
        draw.rectangle(
            [margin_left, y, line_end, y + 3],
            fill=(50, 50, 50)
        )

    # Add a darker edge on one side (simulating book fold)
    fold_side = random.choice(['left', 'right'])
    fold_width = random.randint(30, 80)

    if fold_side == 'left':
        for x in range(fold_width):
            alpha = int(255 * (fold_width - x) / fold_width * 0.3)
            for y in range(height):
                pixel = img.getpixel((x, y))
                new_pixel = tuple(max(0, c - alpha) for c in pixel)
                img.putpixel((x, y), new_pixel)
    else:
        for x in range(width - fold_width, width):
            alpha = int(255 * (x - (width - fold_width)) / fold_width * 0.3)
            for y in range(height):
                pixel = img.getpixel((x, y))
                new_pixel = tuple(max(0, c - alpha) for c in pixel)
                img.putpixel((x, y), new_pixel)

    return img

# =======================
# DATA GENERATION
# =======================

def generate_identifier(index):
    """Generate a unique identifier for an image."""
    return f"IMG_{index:04d}"

def generate_date():
    """Generate a random date in the past."""
    days_ago = random.randint(0, 3650)  # Up to 10 years ago
    date = datetime.now() - timedelta(days=days_ago)
    return date.strftime("%Y-%m-%d")

def generate_test_data(num_documents, images_per_doc, use_nested_folders):
    """
    Generate test data structure.

    Returns:
        tuple: (documents_data, images_data, folder_structure)
    """
    documents_data = []
    images_data = []
    folder_structure = {}

    image_counter = 1

    for doc_idx in range(num_documents):
        # Decide if this document should use nested folders
        use_folder = use_nested_folders and (doc_idx % 2 == 0 or num_documents <= 3)

        # Generate document metadata
        doc_id = f"DOC_{doc_idx + 1:03d}"
        title_it = DOCUMENT_TITLES_IT[doc_idx % len(DOCUMENT_TITLES_IT)]
        title_en = DOCUMENT_TITLES_EN[doc_idx % len(DOCUMENT_TITLES_EN)]
        title_de = DOCUMENT_TITLES_DE[doc_idx % len(DOCUMENT_TITLES_DE)]

        folder_name = f"Archivio_{doc_idx + 1:02d}" if use_folder else None

        # Assign to an archive
        archive_options = []
        for arc in ARCHIVES:
            archive_options.append(arc)
            if "children" in arc:
                archive_options.extend(arc["children"])
        
        assigned_archive = random.choice(archive_options)

        document = {
            "id": doc_id,
            "title_it": title_it,
            "title_en": title_en,
            "title_de": title_de,
            "author": random.choice(AUTHORS),
            "category": random.choice(CATEGORIES),
            "material": random.choice(MATERIALS),
            "period": random.choice(PERIODS),
            "active": random.choice(["SI", "NO"]),
            "date": generate_date(),
            "folder": folder_name,
            "archive_path": assigned_archive["path"],
            "archive_name": assigned_archive["name"],
            "parent_archive": assigned_archive.get("parent"),
            "archive_description_it": assigned_archive["description_it"],
            "archive_description_en": assigned_archive["description_en"],
            "archive_description_de": assigned_archive["description_de"],
        }
        documents_data.append(document)

        # Generate images for this document
        doc_images = []
        for img_idx in range(images_per_doc):
            identifier = generate_identifier(image_counter)

            # Random image format and dimensions
            img_format = random.choice(["JPEG", "PNG", "TIFF"])
            extension = {"JPEG": "jpg", "PNG": "png", "TIFF": "tif"}[img_format]

            # Some images look like book pages (for testing crop)
            is_book_page = random.random() < 0.3

            if is_book_page:
                width, height = 1200, 1600
            else:
                width = random.choice([800, 1024, 1200, 1600])
                height = random.choice([600, 768, 900, 1200])

            image_info = {
                "identifier": identifier,
                "filename": f"{identifier}.{extension}",
                "document_id": doc_id,
                "sequence": img_idx + 1,
                "subject": random.choice(SUBJECTS),
                "description_it": f"Descrizione dettagliata dell'immagine {identifier} in italiano.",
                "description_en": f"Detailed description of image {identifier} in English.",
                "description_de": f"Detaillierte Beschreibung des Bildes {identifier} auf Deutsch.",
                "format": img_format,
                "extension": extension,
                "width": width,
                "height": height,
                "is_book_page": is_book_page,
                "folder": folder_name
            }

            doc_images.append(image_info)
            image_counter += 1

        images_data.extend(doc_images)
        folder_structure[doc_id] = {"document": document, "images": doc_images}

    return documents_data, images_data, folder_structure

# =======================
# FILE GENERATION
# =======================

def create_folder_structure(output_dir, folder_structure):
    """Create folder structure and generate images."""
    input_dir = Path(output_dir) / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating images in {input_dir}...")

    for doc_id, data in folder_structure.items():
        folder_name = data["document"]["folder"]

        for img_info in data["images"]:
            # Determine save path
            if folder_name:
                img_dir = input_dir / folder_name
                img_dir.mkdir(exist_ok=True)
            else:
                img_dir = input_dir

            img_path = img_dir / img_info["filename"]

            # Generate image
            if img_info["is_book_page"]:
                img = generate_book_page_image(img_info["width"], img_info["height"])
            else:
                img = generate_random_image(img_info["width"], img_info["height"], img_info["format"])

            # Save with appropriate format
            if img_info["format"] == "JPEG":
                img.save(img_path, "JPEG", quality=90)
            elif img_info["format"] == "PNG":
                img.save(img_path, "PNG")
            elif img_info["format"] == "TIFF":
                img.save(img_path, "TIFF", compression="tiff_deflate")

            print(f"  Created: {img_path.relative_to(output_dir)}")

def create_csv_file(output_dir, documents_data, images_data):
    """Create CSV file with metadata."""
    csv_path = Path(output_dir) / "input" / "metadata.csv"

    print(f"\nGenerating CSV: {csv_path}...")

    # CSV Headers (multi-language)
    headers = [
        "Codice",           # identifier
        "Titolo[it]",       # groupBy (multi-language)
        "Titolo[en]",
        "Titolo[de]",
        "AUTORE",           # creator
        "MOSTRARE NEL LEGGIO",  # active
        "CATEGORIA",        # tags
        "DATA",             # date
        "Materiale",        # document_type
        "PERIODO",          # period
        "Soggetto",         # nomenclature
        "DIDASCALIA PER LEGGIO[it]",  # rich_description (multi-language)
        "DIDASCALIA PER LEGGIO[en]",
        "DIDASCALIA PER LEGGIO[de]",
        "origin_folder",     # optional origin folder
        "Percorso Archivio",
        "Nome Archivio",
        "Archivio Genitore",
        "Descrizione Archivio[it]",
        "Descrizione Archivio[en]",
        "Descrizione Archivio[de]"
    ]

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        # Group images by document
        for img in images_data:
            # Find document
            doc = next(d for d in documents_data if d["id"] == img["document_id"])

            row = [
                img["identifier"],
                doc["title_it"],
                doc["title_en"],
                doc["title_de"],
                doc["author"],
                doc["active"],
                doc["category"],
                doc["date"],
                doc["material"],
                doc["period"],
                img["subject"],
                img["description_it"],
                img["description_en"],
                img["description_de"],
                img["folder"] if img["folder"] else "",
                doc["archive_path"],
                doc["archive_name"],
                doc["parent_archive"] if doc["parent_archive"] else "",
                doc["archive_description_it"],
                doc["archive_description_en"],
                doc["archive_description_de"],
            ]
            writer.writerow(row)

    print(f"  Created CSV with {len(images_data)} rows")

def create_json_mapping(output_dir):
    """Create custom JSON mapping file."""
    mapping = {
        "document": {
            "identifier": "Codice",
            "groupBy": "Titolo",
            "origin_folder": "origin_folder",
            "title": "Titolo",
            "creator": "AUTORE",
            "active": "MOSTRARE NEL LEGGIO",
            "tags": "CATEGORIA",
            "date": "DATA",
            "document_type": "Materiale",
            "periodo": "PERIODO",
            "metadata_available": True,
            "metadata_just_year": False,
            "archive_path": "Percorso Archivio",
            "archive_name": "Nome Archivio",
            "parent_archive": "Archivio Genitore",
            "archive_description_prefix": "Descrizione Archivio"
        },
        "image": {
            "filename": "Codice",
            "sequence_number": "1",
            "nomenclature": "Soggetto",
            "usage": "master",
            "code": "Codice",
            "datetime_created": "DATA",
            "rich_description_prefix": "DIDASCALIA PER LEGGIO",
            "active": "MOSTRARE NEL LEGGIO"
        }
    }

    json_path = Path(output_dir) / "input" / "test_csv_map.json"

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated JSON mapping: {json_path}")

def create_readme(output_dir, num_documents, total_images, has_nested):
    """Create README file explaining the test dataset."""
    readme_path = Path(output_dir) / "README.md"

    content = f"""# Test Dataset for Image Processing Leggio

Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Dataset Statistics

- **Documents**: {num_documents}
- **Total Images**: {total_images}
- **Folder Structure**: {"Nested (with origin_folder)" if has_nested else "Flat"}
- **Multi-language**: Yes (IT, EN, DE)

## Contents

### input/
Contains all source images and metadata:
- `metadata.csv` - CSV file with document and image metadata
- `test_csv_map.json` - Custom JSON mapping configuration
- `*.jpg`, `*.png`, `*.tif` - Test images in various formats
- `Archivio_XX/` - Nested folders (if applicable)

### Expected Processing Flow

1. **Select input folder**: Point the app to `input/` folder
2. **Configure options**:
   - Enable/disable image cropping (some images simulate book pages)
   - Enable/disable video optimization (no videos in this dataset)
   - Load custom CSV mapping from `test_csv_map.json` if desired
3. **Process**: Run the processing
4. **Expected output**:
   - Images converted to WebP
   - Thumbnails generated (low_quality, gallery)
   - Organized by document title (groupBy field)
   - JSON metadata per document
   - Final ZIP archive

## CSV Structure

The CSV uses multi-language columns:
- `Titolo[it]`, `Titolo[en]`, `Titolo[de]` - Document titles in 3 languages
- `DIDASCALIA PER LEGGIO[it/en/de]` - Image descriptions in 3 languages
- `origin_folder` - Optional folder path for nested structure testing

## Testing Scenarios

This dataset tests:
1. ✓ Multiple image formats (JPEG, PNG, TIFF)
2. ✓ Multi-language metadata grouping
3. ✓ CSV-based organization with groupBy field
4. ✓ Nested folder structures with origin_folder resolution
5. ✓ Flat folder structures with global file index
6. ✓ Book page images (for testing crop.py algorithm)
7. ✓ Document grouping (multiple images per document)
8. ✓ Active/inactive documents filtering

## Notes

- Some images simulate book pages with fold artifacts (for crop testing)
- Images are randomly generated with colored shapes
- All metadata is realistic but fictional
- File identifiers follow IMG_XXXX format matching CSV Codice column
"""

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\nGenerated README: {readme_path}")

# =======================
# MAIN
# =======================

def main():
    parser = argparse.ArgumentParser(
        description="Generate test dataset for Image Processing Leggio app"
    )
    parser.add_argument(
        "--output", "-o",
        default="test_data",
        help="Output directory (default: test_data)"
    )
    parser.add_argument(
        "--documents", "-d",
        type=int,
        default=5,
        help="Number of documents to generate (default: 5)"
    )
    parser.add_argument(
        "--images-per-doc", "-i",
        type=int,
        default=4,
        help="Images per document (default: 4)"
    )
    parser.add_argument(
        "--nested",
        action="store_true",
        default=True,
        help="Create nested folder structure (default: True)"
    )
    parser.add_argument(
        "--small",
        action="store_true",
        help="Generate small dataset (3 docs, 2 images each)"
    )
    parser.add_argument(
        "--medium",
        action="store_true",
        help="Generate medium dataset (6 docs, 4 images each)"
    )
    parser.add_argument(
        "--large",
        action="store_true",
        help="Generate large dataset (12 docs, 6 images each)"
    )

    args = parser.parse_args()

    # Handle presets
    if args.small:
        args.documents = 3
        args.images_per_doc = 2
    elif args.medium:
        args.documents = 6
        args.images_per_doc = 4
    elif args.large:
        args.documents = 12
        args.images_per_doc = 6

    total_images = args.documents * args.images_per_doc

    print("=" * 60)
    print("Image Processing Leggio - Test Data Generator")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Output directory: {args.output}")
    print(f"  Documents: {args.documents}")
    print(f"  Images per document: {args.images_per_doc}")
    print(f"  Total images: {total_images}")
    print(f"  Nested folders: {args.nested}")
    print()

    # Generate data structure
    print("Generating data structure...")
    documents_data, images_data, folder_structure = generate_test_data(
        args.documents,
        args.images_per_doc,
        args.nested
    )

    # Create folder structure and images
    create_folder_structure(args.output, folder_structure)

    # Create CSV
    create_csv_file(args.output, documents_data, images_data)

    # Create JSON mapping
    create_json_mapping(args.output)

    # Create README
    create_readme(args.output, args.documents, total_images, args.nested)

    print("\n" + "=" * 60)
    print("✓ Test dataset generated successfully!")
    print("=" * 60)
    print(f"\nTo use this dataset:")
    print(f"  1. Open the Image Processing Leggio app")
    print(f"  2. Select the '{args.output}/input/' folder")
    print(f"  3. Optionally load '{args.output}/input/test_csv_map.json'")
    print(f"  4. Configure processing options and run")
    print()

if __name__ == "__main__":
    main()
