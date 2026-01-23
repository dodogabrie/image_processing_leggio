#!/usr/bin/env python3
"""
ICCD Renamer Module
Applica le regole di naming ICCD secondo convenzioni definite in desiderata.md
Gestisce logica crop (fold detection) per renaming intelligente delle pagine
"""

import os
from typing import Optional, Tuple, List
from dataclasses import dataclass
from xml_processor import ImageMapping


@dataclass
class CropResult:
    """Risultato del processing crop.py"""
    fold_detected: bool
    left_file: Optional[str] = None
    right_file: Optional[str] = None
    single_file: Optional[str] = None
    processing_logs: str = ""
    original_filename: str = ""
    original_file_path: str = ""  # Path to original file for metadata preservation


class ICCDRenamer:
    """
    Gestisce la rinomina dei file secondo convenzioni ICCD
    Implementa le regole definite in desiderata.md
    """

    def __init__(self):
        self.renamed_files = []

    def generate_iccd_filename(self, mapping: ImageMapping, crop_result: CropResult,
                             side: Optional[str] = None) -> str:
        """
        Genera filename ICCD secondo convenzioni desiderata.md

        Args:
            mapping: Mapping XML per l'immagine
            crop_result: Risultato del processing crop
            side: 'left' o 'right' se specificato

        Returns:
            Filename ICCD formattato con estensione originale
        """
        print(f"[DEBUG] Generating ICCD filename - File: {mapping.original_filename}, Page: {mapping.page_number}, Side: {side}, Fold: {crop_result.fold_detected}")
        # Estrai estensione originale
        original_ext = os.path.splitext(mapping.original_filename)[1]

        if mapping.has_nct and mapping.nct_code:
            # Schema CON NCT: ICCD_1000000000_01_S0001_01
            return self._generate_nct_filename(mapping, crop_result, side, original_ext)
        else:
            # Schema SENZA NCT: ICCD_FSC00001-0001_01_S0001_01
            return self._generate_non_nct_filename(mapping, crop_result, side, original_ext)

    def _generate_nct_filename(self, mapping: ImageMapping, crop_result: CropResult,
                             side: Optional[str] = None, original_ext: str = ".tiff") -> str:
        """Genera filename per schema CON NCT"""

        # Formato: ICCD_1200143419_01_S0001_01
        nct_code = mapping.nct_code

        # Numero progressivo (scheda = 01, foto = 02, etc.)
        progressive_num = self._get_progressive_number(mapping.document_type)

        # Tipologia documento
        doc_type = mapping.document_type
        doc_number = mapping.sequence_number

        # Numero pagina con logica crop
        page_number = self._calculate_page_number(mapping.page_number, crop_result, side)

        filename = f"ICCD_{nct_code}_{progressive_num:02d}_{doc_type}{doc_number}_{page_number:02d}{original_ext}"
        return filename

    def _generate_non_nct_filename(self, mapping: ImageMapping, crop_result: CropResult,
                                 side: Optional[str] = None, original_ext: str = ".tiff") -> str:
        """Genera filename per schema SENZA NCT"""

        # Formato: ICCD_FSC00001-0001_01_S0001_01
        fascicolo = f"FSC{int(mapping.fascicolo_number):05d}"
        oggetto = f"{int(mapping.oggetto_number):04d}"

        # Numero progressivo
        progressive_num = self._get_progressive_number(mapping.document_type)

        # Tipologia documento
        doc_type = mapping.document_type
        doc_number = mapping.sequence_number

        # Numero pagina con logica crop
        page_number = self._calculate_page_number(mapping.page_number, crop_result, side)

        filename = f"ICCD_{fascicolo}-{oggetto}_{progressive_num:02d}_{doc_type}{doc_number}_{page_number:02d}{original_ext}"
        print(f"[DEBUG] Generated filename: {filename}")
        return filename

    def _get_progressive_number(self, document_type: str) -> int:
        """
        Ottieni numero progressivo secondo ordine desiderata.md:
        Schede -> Allegati -> Foto -> Disegni
        """
        type_order = {'S': 1, 'A': 2, 'F': 3, 'P': 4}
        return type_order.get(document_type, 1)

    def _calculate_page_number(self, original_page: int, crop_result: CropResult,
                             side: Optional[str] = None) -> int:
        """
        Calcola numero pagina finale secondo regole desiderata.md

        Regole crop:
        - Pagina 1 + crop -> pagina 4 (left), pagina 1 (right)
        - Pagina 2 + crop -> pagina 2 (left), pagina 3 (right)
        - No crop -> mantieni numerazione originale
        """
        if not crop_result.fold_detected or side is None:
            # No crop o no side specified
            return original_page

        # Applica regole split secondo desiderata.md
        if original_page == 1:
            return 4 if side == 'left' else 1
        elif original_page == 2:
            return 2 if side == 'left' else 3
        else:
            # Per pagine > 2, mantieni logica sequenziale
            # Pagina N -> (N*2, N*2+1)
            return (original_page * 2) if side == 'left' else (original_page * 2 + 1)

    def handle_page_splitting(self, mapping: ImageMapping, crop_result: CropResult) -> List[Tuple[str, str, str]]:
        """
        Gestisce split delle pagine quando fold è rilevato

        Returns:
            Lista di tuple (source_file, target_filename, original_file_path)
        """
        renamings = []

        if crop_result.fold_detected:
            # Fold rilevato - genera nomi per left e right
            if crop_result.left_file:
                left_name = self.generate_iccd_filename(mapping, crop_result, 'left')
                renamings.append((crop_result.left_file, left_name, crop_result.original_file_path))

            if crop_result.right_file:
                right_name = self.generate_iccd_filename(mapping, crop_result, 'right')
                renamings.append((crop_result.right_file, right_name, crop_result.original_file_path))
        else:
            # No fold - rinomina file singolo
            if crop_result.single_file:
                single_name = self.generate_iccd_filename(mapping, crop_result)
                renamings.append((crop_result.single_file, single_name, crop_result.original_file_path))

        return renamings

    def apply_naming_convention(self, source_file: str, target_filename: str,
                              output_dir: str, original_file_for_metadata: str = "") -> bool:
        """
        Applica effettivamente la rinomina del file

        Args:
            source_file: File sorgente (processato)
            target_filename: Nome target ICCD
            output_dir: Directory di output
            original_file_for_metadata: File originale per preservare metadati

        Returns:
            True se rinomina riuscita
        """
        try:
            # Assicurati che output directory esista
            os.makedirs(output_dir, exist_ok=True)

            # Path completo target
            target_path = os.path.join(output_dir, target_filename)

            # Verifica che source file esista
            if not os.path.exists(source_file):
                print(f"[ERROR] Source file not found: {source_file}")
                return False

            # Check for conflicts but don't auto-resolve - ICCD logic should prevent conflicts
            if os.path.exists(target_path):
                print(f"[WARNING] Target file already exists: {target_path} - will OVERWRITE")
                # Remove existing file to prevent conflicts
                os.remove(target_path)
                print(f"[INFO] Removed existing file to avoid conflicts")

            # Save with metadata preservation
            try:
                # Import the metadata-preserving save function
                import sys
                current_dir = os.path.dirname(os.path.abspath(__file__))
                src_path = os.path.join(current_dir, 'src')
                if src_path not in sys.path:
                    sys.path.insert(0, src_path)

                from contour_detector.utils import save_image_with_metadata
                import cv2

                # Load image and save with metadata preservation
                image_array = cv2.imread(source_file)
                if image_array is not None:
                    # Use original file for metadata if provided, otherwise use processed file
                    metadata_source = original_file_for_metadata if original_file_for_metadata and os.path.exists(original_file_for_metadata) else source_file
                    metadata_info = save_image_with_metadata(
                        image_array, target_path, metadata_source, use_compression=True
                    )

                    if original_file_for_metadata and metadata_source == original_file_for_metadata:
                        print(f"[OK] Metadata preserved from original file: {os.path.basename(original_file_for_metadata)}")
                    elif original_file_for_metadata:
                        print(f"[WARNING] Original file not found, using processed file for metadata: {os.path.basename(source_file)}")

                    if metadata_info.get("saved_successfully", False):
                        print(f"[OK] Renamed with metadata: {os.path.basename(source_file)} -> {target_filename}")
                    else:
                        print(f"[WARNING] Renamed but metadata issue: {os.path.basename(source_file)} -> {target_filename}")
                else:
                    raise Exception("Could not load image with cv2")

            except Exception as e:
                # Fallback to simple copy
                print(f"[WARNING] Metadata preservation failed ({e}), using fallback copy")
                import shutil
                shutil.copy2(source_file, target_path)
                print(f"[OK] Renamed (fallback): {os.path.basename(source_file)} -> {target_filename}")

            # Traccia rinomina
            self.renamed_files.append({
                'source': source_file,
                'target': target_path,
                'target_filename': target_filename
            })

            return True

        except Exception as e:
            print(f"[ERROR] Error renaming {source_file}: {e}")
            return False

    def _generate_unique_filename(self, filepath: str) -> str:
        """Genera filename unico in caso di conflitti"""
        base, ext = os.path.splitext(filepath)
        counter = 1

        while os.path.exists(f"{base}_{counter:02d}{ext}"):
            counter += 1

        return f"{base}_{counter:02d}{ext}"

    def create_iccd_directory_structure(self, output_base_dir: str,
                                      mappings: List[ImageMapping]) -> dict:
        """
        Crea struttura directory ICCD organizzata per fascicolo

        Returns:
            Dizionario mapping fascicolo -> directory path
        """
        fascicolo_dirs = {}

        for mapping in mappings:
            if mapping.has_nct and mapping.nct_code:
                # Schema CON NCT
                dir_name = f"ICCD_{mapping.nct_code}"
            else:
                # Schema SENZA NCT
                fascicolo = f"FSC{int(mapping.fascicolo_number):05d}"
                dir_name = f"ICCD_{fascicolo}"

            dir_path = os.path.join(output_base_dir, dir_name)

            if dir_name not in fascicolo_dirs:
                os.makedirs(dir_path, exist_ok=True)
                fascicolo_dirs[dir_name] = dir_path
                print(f"[INFO] Created directory: {dir_name}")

        return fascicolo_dirs

    def get_target_directory(self, mapping: ImageMapping, fascicolo_dirs: dict) -> str:
        """Ottieni directory target per un mapping specifico"""
        if mapping.has_nct and mapping.nct_code:
            dir_name = f"ICCD_{mapping.nct_code}"
        else:
            fascicolo = f"FSC{int(mapping.fascicolo_number):05d}"
            dir_name = f"ICCD_{fascicolo}"

        return fascicolo_dirs.get(dir_name, "")

    def validate_iccd_filename(self, filename: str) -> bool:
        """
        Valida se un filename segue le convenzioni ICCD

        Args:
            filename: Nome file da validare

        Returns:
            True se il filename è valido secondo le convenzioni ICCD
        """
        import re

        # Pattern per schema CON NCT: ICCD_1200143419_01_S0001_01.tiff
        nct_pattern = r'^ICCD_\d{10}_\d{2}_[SAFP]\d{4}_\d{2}\.\w+$'

        # Pattern per schema SENZA NCT: ICCD_FSC00001-0001_01_S0001_01.tiff
        non_nct_pattern = r'^ICCD_FSC\d{5}-\d{4}_\d{2}_[SAFP]\d{4}_\d{2}\.\w+$'

        return bool(re.match(nct_pattern, filename) or re.match(non_nct_pattern, filename))

    def generate_processing_report(self, output_file: str):
        """Genera report delle rinominazioni effettuate"""
        import json
        from datetime import datetime

        report = {
            'timestamp': datetime.now().isoformat(),
            'total_renamed': len(self.renamed_files),
            'files': self.renamed_files
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"[INFO] Processing report saved: {output_file}")


def analyze_crop_output(output_path: str, was_cropped: bool,
                       original_filename: str, original_file_path: str = "") -> CropResult:
    """
    Analizza output del crop per determinare se fold è stato rilevato
    Si basa sui file _left/_right generati dal crop.py

    Args:
        output_path: Path del file processato
        was_cropped: Se il crop ha rilevato fold
        original_filename: Nome file originale
        original_file_path: Path del file originale per preservare metadati

    Returns:
        CropResult con informazioni sui file generati
    """
    # Controlla se esistono file _left e _right (fold rilevato)
    base_dir = os.path.dirname(output_path)
    base_name = os.path.splitext(os.path.basename(output_path))[0]

    # Rimuovi suffissi _left/_right se presenti nel nome
    if base_name.endswith('_left'):
        base_name = base_name[:-5]
    elif base_name.endswith('_right'):
        base_name = base_name[:-6]

    left_file = os.path.join(base_dir, f"{base_name}_left.jpg")
    right_file = os.path.join(base_dir, f"{base_name}_right.jpg")

    if os.path.exists(left_file) and os.path.exists(right_file):
        # Fold rilevato
        return CropResult(
            fold_detected=True,
            left_file=left_file,
            right_file=right_file,
            original_filename=original_filename,
            original_file_path=original_file_path
        )
    else:
        # No fold - file singolo
        return CropResult(
            fold_detected=False,
            single_file=output_path,
            original_filename=original_filename,
            original_file_path=original_file_path
        )


if __name__ == "__main__":
    # Test del modulo
    renamer = ICCDRenamer()

    test_filenames = [
        "ICCD_FSC01351-0001_01_S0001_01.tiff",
        "ICCD_1200143419_01_S0001_01.tiff"
    ]

    for filename in test_filenames:
        print(f"Test: {filename}")