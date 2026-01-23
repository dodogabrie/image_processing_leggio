#!/usr/bin/env python3
"""
XML Processor per parsing file OBJ.xml
Estrae mappings filename -> metadati ICCD secondo convenzioni desiderata.md
"""

import os
import glob
from typing import Dict, List, Optional, NamedTuple
from dataclasses import dataclass
from lxml import etree
import re


@dataclass
class ImageMapping:
    """Struttura dati per mapping immagine -> metadati ICCD"""
    original_filename: str
    fascicolo_number: str
    oggetto_number: str
    document_type: str  # S/A/F/P
    sequence_number: str
    page_number: int
    object_folder: str
    has_nct: bool = False
    nct_code: str = ""
    # New fields for subdirectory support
    full_path: str = ""  # Full path to source file
    subdir: str = None   # Subdirectory name (tiff, jpeg300, etc.)


class XMLProcessorError(Exception):
    """Eccezione per errori di processing XML"""
    pass


class XMLProcessor:
    """Parser per file XML delle object ICCD"""

    def __init__(self):
        self.mappings: List[ImageMapping] = []

    def discover_object_files(self, input_dir: str) -> List[tuple]:
        """
        Scopre tutte le coppie Folder + Folder.xml nell'input directory

        Returns:
            List di tuple (folder_path, xml_file_path)
        """
        folder_pairs = []

        # Pattern per trovare TUTTI i file XML
        xml_pattern = os.path.join(input_dir, "*.xml")
        xml_files = glob.glob(xml_pattern)

        for xml_file in xml_files:
            # Estrai nome base dal filename XML
            xml_basename = os.path.basename(xml_file)
            folder_name = xml_basename.replace('.xml', '')

            # Cerca cartella corrispondente con stesso nome
            folder_path = os.path.join(input_dir, folder_name)

            if os.path.isdir(folder_path):
                folder_pairs.append((folder_path, xml_file))
            else:
                print(f"[WARNING] Found {xml_file} but no corresponding folder {folder_path}")

        print(f"[INFO] Discovered {len(folder_pairs)} folder-XML pairs")
        return folder_pairs

    def parse_object_xml(self, xml_file_path: str) -> Dict:
        """
        Parsa un singolo file object_XX.xml

        Args:
            xml_file_path: Path al file XML da parsare

        Returns:
            Dizionario con metadati estratti
        """
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(xml_file_path, parser)
            root = tree.getroot()

            # Estrai informazioni base dalla struttura XML
            xml_data = {
                'xml_file': xml_file_path,
                'root_tag': root.tag,
                'namespaces': root.nsmap,
                'elements': []
            }

            # Parsing ricorsivo degli elementi
            self._parse_elements_recursive(root, xml_data['elements'])

            return xml_data

        except etree.XMLSyntaxError as e:
            raise XMLProcessorError(f"Errore parsing XML {xml_file_path}: {e}")
        except Exception as e:
            raise XMLProcessorError(f"Errore generico parsing {xml_file_path}: {e}")

    def _parse_elements_recursive(self, element, elements_list):
        """Parsing ricorsivo degli elementi XML"""
        # Handle both string tags and lxml element tags
        tag_name = element.tag if isinstance(element.tag, str) else str(element.tag)

        elem_data = {
            'tag': tag_name,
            'text': element.text.strip() if element.text else '',
            'attributes': dict(element.attrib),
            'children': []
        }

        for child in element:
            self._parse_elements_recursive(child, elem_data['children'])

        elements_list.append(elem_data)


    def extract_image_mappings_sequential(self, xml_data: Dict, folder_path: str,
                                        process_jpg: bool = True, process_tiff: bool = True) -> List[ImageMapping]:
        """
        NEW: Estrae mappings usando approccio sequenziale XML (risolve bug Windows/Linux)

        Args:
            xml_data: Dati XML parsati
            folder_path: Path alla cartella con immagini
            process_jpg: Se processare file .jpg/.jpeg
            process_tiff: Se processare file .tiff/.tif

        Returns:
            Lista di ImageMapping objects
        """
        mappings = []

        try:
            # Parse directly from the XML file using lxml
            xml_file = xml_data['xml_file']
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(xml_file, parser)
            root = tree.getroot()

            # Define namespace map
            ns = {'mag': 'http://www.iccu.sbn.it/metaAG1.pdf',
                  'xlink': 'http://www.w3.org/1999/xlink'}

            # Parse fascicoli ranges from <stru> elements
            fascicoli = self._parse_fascicoli_direct(root, ns)
            print(f"[INFO] Found {len(fascicoli)} fascicoli in XML")

            # Process each fascicolo sequentially
            for fascicolo in fascicoli:
                print(f"[INFO] Processing fascicolo {fascicolo['number']} (sequences {fascicolo['start_sequence']}-{fascicolo['stop_sequence']})")

                fascicolo_mappings = self._process_fascicolo_sequential(
                    root, ns, fascicolo, folder_path, process_jpg, process_tiff
                )
                mappings.extend(fascicolo_mappings)

            print(f"[INFO] Sequential processing complete: {len(mappings)} mappings created")

        except Exception as e:
            print(f"[ERROR] Error in sequential XML processing: {e}")

        return mappings

    def _process_fascicolo_sequential(self, root, ns, fascicolo, folder_path,
                                    process_jpg: bool, process_tiff: bool) -> List[ImageMapping]:
        """Process a single fascicolo in XML sequence order"""
        mappings = []
        doc_counters = {'S': 0, 'A': 0, 'F': 0, 'P': 0}

        doc_type_mapping = {
            'Pagina': 'S',  # Scheda
            'Indice': 'A',  # Allegato
            'Carta': 'F',   # Foto
            'Tavola': 'P'   # Disegno
        }

        print(f"   [INFO] Processing fascicolo {fascicolo['number']}")

        # Process sequences in order within fascicolo boundaries
        for seq_num in range(fascicolo['start_sequence'], fascicolo['stop_sequence'] + 1):

            # Find img element for this sequence number
            img_elements = root.xpath(f'.//mag:img[mag:sequence_number/text()="{seq_num}"]', namespaces=ns)

            if not img_elements:
                # Skip missing sequences (gaps in numbering are normal)
                continue

            img = img_elements[0]

            # Extract nomenclature and parse document type + page
            nomenclature_elem = img.xpath('./mag:nomenclature', namespaces=ns)
            if not nomenclature_elem:
                print(f"   [WARNING] No nomenclature found for sequence {seq_num}")
                continue

            nomenclature = nomenclature_elem[0].text
            doc_type, page_num = self._parse_nomenclature_sequential(nomenclature, doc_type_mapping)

            # Increment document counter when we see page 1
            if page_num == 1:
                doc_counters[doc_type] += 1
                print(f"   [INFO] New {doc_type} document #{doc_counters[doc_type]} starting at sequence {seq_num}")

            current_doc_seq = doc_counters[doc_type]

            # Get file paths (both TIFF and JPEG if present)
            files = self._extract_files_from_img_sequential(img, ns, folder_path, process_jpg, process_tiff)

            # Create ImageMapping for each file
            for file_info in files:
                mapping = ImageMapping(
                    original_filename=file_info['filename'],
                    fascicolo_number=str(fascicolo['number']),
                    oggetto_number=f"{current_doc_seq:04d}",  # Object = document sequence
                    document_type=doc_type,
                    sequence_number=f"{current_doc_seq:04d}",  # Same as object
                    page_number=page_num,
                    object_folder=folder_path,
                    full_path=file_info['full_path'],
                    subdir=file_info['subdir']
                )
                mappings.append(mapping)

                print(f"   [MAPPING] {file_info['filename']} -> Fascicolo:{fascicolo['number']} Object:{current_doc_seq:04d} {doc_type}{current_doc_seq:04d}_{page_num:02d}")

        print(f"   [INFO] Fascicolo {fascicolo['number']} complete: {len(mappings)} mappings")
        return mappings

    def _parse_nomenclature_sequential(self, nomenclature: str, doc_type_mapping: dict) -> tuple:
        """Parse nomenclature like 'Pagina: 1', 'Tavola: 2' into (doc_type, page_num)"""
        if not nomenclature:
            return 'S', 1

        # Extract document type and page number
        import re
        match = re.match(r'(Pagina|Tavola|Carta|Indice):\s*(\d+)', nomenclature)
        if match:
            doc_prefix = match.group(1)
            page_num = int(match.group(2))
            doc_type = doc_type_mapping.get(doc_prefix, 'S')
            return doc_type, page_num

        # Handle cases with no page number
        for prefix, doc_type in doc_type_mapping.items():
            if prefix.lower() in nomenclature.lower():
                return doc_type, 1

        return 'S', 1  # Default fallback

    def _extract_files_from_img_sequential(self, img, ns, folder_path, process_jpg: bool, process_tiff: bool) -> List[Dict]:
        """Extract filenames from img element (both main and altimg)"""
        files = []

        # Get main file (usually .tif)
        main_file = img.xpath('./mag:file[@xlink:href]', namespaces=ns)
        if main_file:
            href = main_file[0].get('{http://www.w3.org/1999/xlink}href')
            if href:
                filename = os.path.basename(href)
                # Check if we should process this file type
                ext = os.path.splitext(filename)[1].lower()
                should_process = (
                    (process_tiff and ext in ['.tif', '.tiff']) or
                    (process_jpg and ext in ['.jpg', '.jpeg']) or
                    ext in ['.png']  # Always process PNG
                )

                if should_process:
                    file_info = self._find_file_in_folder(filename, folder_path)
                    if file_info:
                        files.append(file_info)

        # Get altimg file (usually .jpg)
        altimg_file = img.xpath('.//mag:altimg//mag:file[@xlink:href]', namespaces=ns)
        if altimg_file:
            href = altimg_file[0].get('{http://www.w3.org/1999/xlink}href')
            if href:
                filename = os.path.basename(href)
                # Check if we should process this file type
                ext = os.path.splitext(filename)[1].lower()
                should_process = (
                    (process_tiff and ext in ['.tif', '.tiff']) or
                    (process_jpg and ext in ['.jpg', '.jpeg']) or
                    ext in ['.png']  # Always process PNG
                )

                if should_process:
                    file_info = self._find_file_in_folder(filename, folder_path)
                    if file_info:
                        # Avoid duplicates
                        if not any(f['filename'] == filename for f in files):
                            files.append(file_info)

        return files

    def _find_file_in_folder(self, filename: str, folder_path: str) -> Dict:
        """Find file in folder or standard subdirectories and return file info"""
        # Check main directory
        main_path = os.path.join(folder_path, filename)
        if os.path.exists(main_path):
            return {
                'filename': filename,
                'full_path': main_path,
                'subdir': None
            }

        # Check standard subdirectories
        standard_subdirs = ['tiff', 'tif', 'jpeg300', 'jpeg150']
        for subdir_name in standard_subdirs:
            # Case insensitive search
            for item in os.listdir(folder_path):
                if item.lower() == subdir_name.lower():
                    subdir_path = os.path.join(folder_path, item)
                    if os.path.isdir(subdir_path):
                        file_path = os.path.join(subdir_path, filename)
                        if os.path.exists(file_path):
                            return {
                                'filename': filename,
                                'full_path': file_path,
                                'subdir': item
                            }

        return None  # File not found

    def _parse_fascicoli_direct(self, root, ns: Dict) -> List[Dict]:
        """Parse fascicoli ranges from <stru> elements using XPath"""
        fascicoli = []

        try:
            stru_elements = root.xpath('.//mag:stru', namespaces=ns)

            for stru in stru_elements:
                # Get fascicolo number from issue element
                issue_elem = stru.xpath('.//mag:issue', namespaces=ns)
                if not issue_elem:
                    continue

                issue_text = issue_elem[0].text
                import re
                match = re.search(r'fasc\.\s*(\d+)', issue_text)
                if not match:
                    continue

                fascicolo_number = int(match.group(1))

                # Get start and stop sequence numbers
                start_elem = stru.xpath('.//mag:start', namespaces=ns)
                stop_elem = stru.xpath('.//mag:stop', namespaces=ns)

                if not (start_elem and stop_elem):
                    continue

                start_seq = int(start_elem[0].get('sequence_number'))
                stop_seq = int(stop_elem[0].get('sequence_number'))

                fascicoli.append({
                    'number': fascicolo_number,
                    'start_sequence': start_seq,
                    'stop_sequence': stop_seq
                })

        except Exception as e:
            print(f"[ERROR] Error parsing fascicoli: {e}")

        return fascicoli

    def _get_image_files(self, folder_path: str, process_jpg: bool = True, process_tiff: bool = True) -> List[Dict]:
        """
        Ottieni lista file immagine dalla cartella object e sottocartelle standard.

        Args:
            folder_path: Path alla cartella object
            process_jpg: Se processare .jpg/.jpeg
            process_tiff: Se processare .tiff/.tif

        Returns:
            Lista di dict con 'filename', 'full_path', 'subdir'
        """
        image_extensions = []
        if process_jpg:
            image_extensions.extend(['*.jpg', '*.jpeg'])
        if process_tiff:
            image_extensions.extend(['*.tiff', '*.tif'])
        # Always include PNG
        image_extensions.append('*.png')

        # Standard subdirectories to scan (case insensitive)
        standard_subdirs = ['tif', 'tiff', 'jpeg300', 'jpeg150']

        image_files = []

        # Search in main directory
        for ext in image_extensions:
            pattern = os.path.join(folder_path, ext)
            found_files = glob.glob(pattern) + glob.glob(pattern.upper())
            for file_path in found_files:
                image_files.append({
                    'filename': os.path.basename(file_path),
                    'full_path': file_path,
                    'subdir': None  # Main directory
                })

        # Search in standard subdirectories
        for subdir_name in standard_subdirs:
            # Case insensitive search for subdirectory
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if (os.path.isdir(item_path) and
                    item.lower() == subdir_name.lower()):

                    print(f"   [INFO] Scanning subdirectory: {item}")

                    # Search for images in this subdirectory
                    for ext in image_extensions:
                        pattern = os.path.join(item_path, ext)
                        found_files = glob.glob(pattern) + glob.glob(pattern.upper())
                        for file_path in found_files:
                            image_files.append({
                                'filename': os.path.basename(file_path),
                                'full_path': file_path,
                                'subdir': item  # Actual subdirectory name (preserves case)
                            })
                    break  # Found matching subdirectory

        print(f"   [INFO] Scanning {folder_path} for images (JPG: {process_jpg}, TIFF: {process_tiff})")

        # Group by subdirectory for reporting
        by_subdir = {}
        for file_info in image_files:
            subdir = file_info['subdir'] or 'main'
            if subdir not in by_subdir:
                by_subdir[subdir] = []
            by_subdir[subdir].append(file_info['filename'])

        for subdir, files in by_subdir.items():
            print(f"   [INFO] {subdir}: {len(files)} files - {files[:3]}{'...' if len(files) > 3 else ''}")

        return image_files

    def _infer_document_info(self, base_name: str, index: int) -> tuple:
        """
        Inferisce tipo documento e numero sequenza dal filename

        Returns:
            (document_type, sequence_number)
        """
        # Logica base di inferenza - può essere migliorata con pattern specifici

        # Se il filename contiene pattern specifici
        if 'foto' in base_name.lower() or 'f_' in base_name.lower():
            return 'F', f"{index+1:04d}"
        elif 'disegno' in base_name.lower() or 'p_' in base_name.lower():
            return 'P', f"{index+1:04d}"
        elif 'allegato' in base_name.lower() or 'a_' in base_name.lower():
            return 'A', f"{index+1:04d}"
        else:
            # Default: scheda
            return 'S', f"{index+1:04d}"


    def process_all_objects(self, input_dir: str, process_jpg: bool = True, process_tiff: bool = True) -> List[ImageMapping]:
        """
        Processa tutte le object nell'input directory

        Args:
            input_dir: Directory contenente le object
            process_jpg: Se processare file .jpg/.jpeg
            process_tiff: Se processare file .tiff/.tif

        Returns:
            Lista completa di tutti i mappings estratti
        """
        all_mappings = []

        # Scopri tutte le coppie Folder-XML
        folder_pairs = self.discover_object_files(input_dir)

        for folder_path, xml_file in folder_pairs:
            print(f"[INFO] Processing {os.path.basename(xml_file)}...")

            try:
                # Parsa XML
                xml_data = self.parse_object_xml(xml_file)

                # Estrai mappings usando approccio sequenziale (risolve bug Windows/Linux)
                print("[INFO] Using sequential XML processing to avoid Windows/Linux differences")
                mappings = self.extract_image_mappings_sequential(xml_data, folder_path, process_jpg, process_tiff)

                print(f"[OK] Extracted {len(mappings)} image mappings from {os.path.basename(xml_file)}")

                all_mappings.extend(mappings)

            except XMLProcessorError as e:
                print(f"[ERROR] Error processing {xml_file}: {e}")
                continue
            except Exception as e:
                print(f"[ERROR] Unexpected error processing {xml_file}: {e}")
                continue

        self.mappings = all_mappings
        print(f"[INFO] Total mappings extracted: {len(all_mappings)}")

        return all_mappings

    def get_mapping_by_filename(self, filename: str) -> Optional[ImageMapping]:
        """Trova mapping per filename specifico"""
        for mapping in self.mappings:
            if mapping.original_filename == filename:
                return mapping
        return None

    def save_mappings_to_json(self, mappings: List[ImageMapping], output_file: str,
                            include_iccd_names: bool = True) -> bool:
        """
        Salva i mappings completi in formato JSON per debug e verifica

        Args:
            mappings: Lista di ImageMapping da salvare
            output_file: Path del file JSON di output
            include_iccd_names: Se includere i nomi ICCD generati

        Returns:
            True se salvato con successo
        """
        try:
            import json
            from datetime import datetime

            # Convert mappings to JSON-serializable format
            json_data = {
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_mappings': len(mappings),
                    'include_iccd_names': include_iccd_names
                },
                'mappings': []
            }

            # Group by fascicolo for better organization
            fascicolo_groups = {}
            for mapping in mappings:
                fasc_num = mapping.fascicolo_number
                if fasc_num not in fascicolo_groups:
                    fascicolo_groups[fasc_num] = []
                fascicolo_groups[fasc_num].append(mapping)

            # Process each fascicolo
            for fasc_num, fasc_mappings in sorted(fascicolo_groups.items(), key=lambda x: int(x[0])):
                fascicolo_data = {
                    'fascicolo_number': fasc_num,
                    'total_images': len(fasc_mappings),
                    'images': []
                }

                # Group by document type within fascicolo
                doc_type_groups = {'S': [], 'A': [], 'F': [], 'P': []}
                for mapping in fasc_mappings:
                    doc_type_groups[mapping.document_type].append(mapping)

                # Process in ICCD order: S, A, F, P
                for doc_type in ['S', 'A', 'F', 'P']:
                    if doc_type_groups[doc_type]:
                        # Sort by sequence number within document type
                        sorted_mappings = sorted(doc_type_groups[doc_type],
                                               key=lambda x: int(x.sequence_number))

                        for mapping in sorted_mappings:
                            mapping_data = {
                                'original_filename': mapping.original_filename,
                                'full_path': mapping.full_path,
                                'subdir': mapping.subdir,
                                'fascicolo_number': mapping.fascicolo_number,
                                'oggetto_number': mapping.oggetto_number,
                                'document_type': mapping.document_type,
                                'document_type_name': self._get_document_type_name(mapping.document_type),
                                'sequence_number': mapping.sequence_number,
                                'page_number': mapping.page_number,
                                'object_folder': mapping.object_folder,
                                'has_nct': mapping.has_nct,
                                'nct_code': mapping.nct_code
                            }

                            # Add ICCD filename if requested
                            if include_iccd_names:
                                mapping_data['iccd_filename'] = self._generate_iccd_filename_preview(mapping)

                            fascicolo_data['images'].append(mapping_data)

                json_data['mappings'].append(fascicolo_data)

            # Add summary statistics
            json_data['summary'] = self._generate_mapping_summary(mappings)

            # Write to file
            output_dir = os.path.dirname(output_file)
            if output_dir:  # Only create directories if there's a directory part
                os.makedirs(output_dir, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)

            print(f"[OK] Mappings saved to: {output_file}")
            print(f"[INFO] Total mappings: {len(mappings)}")
            print(f"[INFO] Fascicoli: {len(fascicolo_groups)}")

            return True

        except Exception as e:
            print(f"[ERROR] Error saving mappings to JSON: {e}")
            return False

    def _get_document_type_name(self, doc_type: str) -> str:
        """Get human-readable document type name"""
        type_names = {
            'S': 'Scheda',
            'A': 'Allegato',
            'F': 'Foto',
            'P': 'Disegno'
        }
        return type_names.get(doc_type, 'Unknown')

    def _generate_iccd_filename_preview(self, mapping: ImageMapping) -> str:
        """Generate ICCD filename for preview (without crop logic)"""
        ext = os.path.splitext(mapping.original_filename)[1]

        if mapping.has_nct and mapping.nct_code:
            # Schema CON NCT
            progressive = self._get_progressive_number_for_preview(mapping.document_type)
            return f"ICCD_{mapping.nct_code}_{progressive:02d}_{mapping.document_type}{mapping.sequence_number}_{mapping.page_number:02d}{ext}"
        else:
            # Schema SENZA NCT
            fascicolo = f"FSC{int(mapping.fascicolo_number):05d}"
            progressive = self._get_progressive_number_for_preview(mapping.document_type)
            return f"ICCD_{fascicolo}-{mapping.oggetto_number}_{progressive:02d}_{mapping.document_type}{mapping.sequence_number}_{mapping.page_number:02d}{ext}"

    def _get_progressive_number_for_preview(self, document_type: str) -> int:
        """Get progressive number for ICCD filename preview"""
        type_order = {'S': 1, 'A': 2, 'F': 3, 'P': 4}
        return type_order.get(document_type, 1)

    def _generate_mapping_summary(self, mappings: List[ImageMapping]) -> dict:
        """Generate summary statistics for mappings"""
        summary = {
            'total_images': len(mappings),
            'by_fascicolo': {},
            'by_document_type': {'S': 0, 'A': 0, 'F': 0, 'P': 0},
            'by_file_type': {},
            'has_subdirectories': False,
            'subdirectories': set()
        }

        for mapping in mappings:
            # Count by fascicolo
            fasc_num = mapping.fascicolo_number
            if fasc_num not in summary['by_fascicolo']:
                summary['by_fascicolo'][fasc_num] = 0
            summary['by_fascicolo'][fasc_num] += 1

            # Count by document type
            summary['by_document_type'][mapping.document_type] += 1

            # Count by file type
            ext = os.path.splitext(mapping.original_filename)[1].lower()
            if ext not in summary['by_file_type']:
                summary['by_file_type'][ext] = 0
            summary['by_file_type'][ext] += 1

            # Track subdirectories
            if mapping.subdir:
                summary['has_subdirectories'] = True
                summary['subdirectories'].add(mapping.subdir)

        # Convert set to list for JSON serialization
        summary['subdirectories'] = list(summary['subdirectories'])

        return summary

    def export_xml_mappings_to_json(self, xml_file_path: str, folder_path: str,
                                  output_json_path: str, process_jpg: bool = True,
                                  process_tiff: bool = True) -> bool:
        """
        Convenience method to export mappings from a single XML file to JSON

        Args:
            xml_file_path: Path to XML file
            folder_path: Path to image folder
            output_json_path: Path for output JSON file
            process_jpg: Whether to process .jpg/.jpeg files
            process_tiff: Whether to process .tiff/.tif files

        Returns:
            True if successful
        """
        try:
            # Parse XML
            xml_data = self.parse_object_xml(xml_file_path)

            # Extract mappings using sequential processing
            mappings = self.extract_image_mappings_sequential(xml_data, folder_path, process_jpg, process_tiff)

            if not mappings:
                print(f"[WARNING] No mappings found for {xml_file_path}")
                return False

            # Save to JSON
            return self.save_mappings_to_json(mappings, output_json_path, include_iccd_names=True)

        except Exception as e:
            print(f"[ERROR] Error exporting XML mappings to JSON: {e}")
            return False


def has_object_structure(input_dir: str) -> bool:
    """Verifica se l'input directory contiene struttura Folder+XML"""
    if not os.path.exists(input_dir) or not os.path.isdir(input_dir):
        return False

    # Cerca TUTTI i file XML
    xml_pattern = os.path.join(input_dir, "*.xml")
    xml_files = glob.glob(xml_pattern)

    if not xml_files:
        return False

    # Verifica che per ogni XML esista cartella corrispondente con immagini
    for xml_file in xml_files:
        xml_basename = os.path.basename(xml_file)
        folder_name = xml_basename.replace('.xml', '')
        folder_path = os.path.join(input_dir, folder_name)

        if os.path.isdir(folder_path):
            # Verifica che la cartella contenga immagini (root o sottocartelle standard)
            image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.tiff', '*.tif']
            has_images = False

            # 1. Cerca immagini nella cartella principale
            for ext in image_extensions:
                pattern = os.path.join(folder_path, ext)
                if glob.glob(pattern) or glob.glob(pattern.upper()):
                    has_images = True
                    break

            # 2. Se non trovate, cerca nelle sottocartelle standard ICCD
            if not has_images:
                standard_subdirs = ['tiff', 'tif', 'jpeg300', 'jpeg150']
                for subdir in standard_subdirs:
                    subdir_path = os.path.join(folder_path, subdir)
                    if os.path.isdir(subdir_path):
                        for ext in image_extensions:
                            pattern = os.path.join(subdir_path, ext)
                            if glob.glob(pattern) or glob.glob(pattern.upper()):
                                has_images = True
                                break
                        if has_images:
                            break

            if has_images:
                return True

    return False


if __name__ == "__main__":
    # Test del modulo
    import sys

    if len(sys.argv) < 2:
        print("Usage: python xml_processor.py <input_dir>")
        sys.exit(1)

    input_dir = sys.argv[1]
    processor = XMLProcessor()
    mappings = processor.process_all_objects(input_dir)

    for mapping in mappings:
        print(f"{mapping.original_filename} -> {mapping.fascicolo_number} {mapping.document_type}")