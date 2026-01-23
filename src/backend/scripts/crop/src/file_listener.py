"""
file_listener.py

Modulo per monitorare la cartella di output e rinominare i file secondo una mappa predefinita.
"""

import os
import time
import threading
from pathlib import Path

# Try to import watchdog, fall back to polling if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    print("Warning: watchdog not available, using polling mode for file monitoring")


class FileRenameHandler:
    """Handler per rinominare i file secondo una mappa predefinita."""
    
    def __init__(self, rename_map, verbose=True):
        """
        Inizializza il handler.
        
        Args:
            rename_map (dict): Mappa di rinominazione {pattern_to_find: replacement}
            verbose (bool): Se stampare informazioni sulle operazioni
        """
        self.rename_map = rename_map
        self.verbose = verbose
        self.processed_files = set()  # Evita di processare lo stesso file più volte
        
    def on_created(self, event):
        """Chiamato quando viene creato un nuovo file."""
        if hasattr(event, 'is_directory') and not event.is_directory:
            self.process_file(event.src_path)
    
    def on_moved(self, event):
        """Chiamato quando un file viene spostato/rinominato."""
        if hasattr(event, 'is_directory') and not event.is_directory:
            self.process_file(event.dest_path)
    
    def process_file(self, file_path):
        """
        Processa un file per il rinominamento se corrisponde ai pattern.
        
        Args:
            file_path (str): Percorso del file da processare
        """
        # Attendi che il file sia completamente scritto
        time.sleep(0.5)
        
        # Evita di processare lo stesso file più volte
        if file_path in self.processed_files:
            return
        
        if not os.path.exists(file_path):
            return
            
        file_name = os.path.basename(file_path)
        
        # Controlla se il file corrisponde a uno dei pattern da rinominare
        for pattern, replacement in self.rename_map.items():
            if pattern in file_name:
                new_name = file_name.replace(pattern, replacement)
                new_path = os.path.join(os.path.dirname(file_path), new_name)
                
                try:
                    # Rinomina il file
                    os.rename(file_path, new_path)
                    self.processed_files.add(file_path)
                    self.processed_files.add(new_path)
                    
                    if self.verbose:
                        print(f"Rinominato: {file_name} -> {new_name}")
                    
                    break  # Esci dopo il primo match per evitare rinominazioni multiple
                    
                except OSError as e:
                    if self.verbose:
                        print(f"Errore durante la rinominazione di {file_name}: {e}")


class FileListener:
    """Classe principale per il monitoraggio e rinominazione dei file."""
    
    def __init__(self, output_dir, rename_map, verbose=True):
        """
        Inizializza il file listener.
        
        Args:
            output_dir (str): Directory da monitorare
            rename_map (dict): Mappa di rinominazione
            verbose (bool): Se stampare informazioni sulle operazioni
        """
        self.output_dir = output_dir
        self.rename_map = rename_map
        self.verbose = verbose
        self.observer = None
        self.handler = None
        self.is_running = False
        self.polling_thread = None
        self.use_watchdog = WATCHDOG_AVAILABLE
        
    def start_monitoring(self):
        """Avvia il monitoraggio della directory."""
        if self.is_running:
            if self.verbose:
                print("Il monitoraggio è già attivo.")
            return
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
        self.handler = FileRenameHandler(self.rename_map, self.verbose)
        
        if self.use_watchdog:
            # Use watchdog for real-time monitoring
            from watchdog.events import FileSystemEventHandler
            
            class WatchdogHandler(FileSystemEventHandler):
                def __init__(self, file_handler):
                    self.file_handler = file_handler
                
                def on_created(self, event):
                    self.file_handler.on_created(event)
                
                def on_moved(self, event):
                    self.file_handler.on_moved(event)
            
            self.observer = Observer()
            watchdog_handler = WatchdogHandler(self.handler)
            self.observer.schedule(watchdog_handler, self.output_dir, recursive=True)
            self.observer.start()
        else:
            # Use polling as fallback
            self.polling_thread = threading.Thread(target=self._polling_monitor, daemon=True)
            self.polling_thread.start()
        
        self.is_running = True
        
        if self.verbose:
            mode = "watchdog" if self.use_watchdog else "polling"
            print(f"Avviato monitoraggio ({mode}) della directory: {self.output_dir}")
            print(f"Mappa di rinominazione: {self.rename_map}")
    
    def _polling_monitor(self):
        """Polling fallback monitor."""
        seen_files = set()
        
        while self.is_running:
            try:
                # Check for new files
                for root, dirs, files in os.walk(self.output_dir):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        if file_path not in seen_files:
                            seen_files.add(file_path)
                            # Simulate event for new file
                            class MockEvent:
                                def __init__(self, path):
                                    self.src_path = path
                                    self.is_directory = False
                            
                            self.handler.on_created(MockEvent(file_path))
                
                time.sleep(2)  # Check every 2 seconds
            except Exception as e:
                if self.verbose:
                    print(f"Errore nel polling monitor: {e}")
                time.sleep(5)
    
    def stop_monitoring(self):
        """Ferma il monitoraggio della directory."""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.use_watchdog and self.observer:
            self.observer.stop()
            self.observer.join()
        
        if self.verbose:
            print("Monitoraggio fermato.")
    
    def process_existing_files(self):
        """Processa i file già esistenti nella directory secondo la mappa."""
        if not os.path.exists(self.output_dir):
            return
        
        processed_count = 0
        
        # Processa ricorsivamente tutti i file nella directory
        for root, dirs, files in os.walk(self.output_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                
                # Controlla se il file corrisponde a uno dei pattern
                for pattern, replacement in self.rename_map.items():
                    if pattern in file_name:
                        new_name = file_name.replace(pattern, replacement)
                        new_path = os.path.join(root, new_name)
                        
                        if file_path != new_path:  # Evita rinominazioni inutili
                            try:
                                os.rename(file_path, new_path)
                                processed_count += 1
                                
                                if self.verbose:
                                    print(f"Rinominato file esistente: {file_name} -> {new_name}")
                                
                                break  # Esci dopo il primo match
                                
                            except OSError as e:
                                if self.verbose:
                                    print(f"Errore durante la rinominazione di {file_name}: {e}")
        
        if self.verbose and processed_count > 0:
            print(f"Processati {processed_count} file esistenti.")
    
    def update_rename_map(self, new_map):
        """
        Aggiorna la mappa di rinominazione.
        
        Args:
            new_map (dict): Nuova mappa di rinominazione
        """
        self.rename_map = new_map
        if self.handler:
            self.handler.rename_map = new_map
        
        if self.verbose:
            print(f"Mappa di rinominazione aggiornata: {self.rename_map}")


def create_default_rename_map():
    """
    Crea una mappa di rinominazione di esempio.
    
    Returns:
        dict: Mappa di rinominazione di default
    """
    return {
        "_01_right": "_01",
        "_01_left": "_04", 
        "_02_left": "_02",
        "_02_right": "_03",
    }


def start_file_listener_thread(output_dir, rename_map=None, verbose=True):
    """
    Avvia il file listener in un thread separato.
    
    Args:
        output_dir (str): Directory da monitorare
        rename_map (dict): Mappa di rinominazione (opzionale)
        verbose (bool): Se stampare informazioni
    
    Returns:
        FileListener: Istanza del file listener
    """
    if rename_map is None:
        rename_map = create_default_rename_map()
    
    listener = FileListener(output_dir, rename_map, verbose)
    
    # Processa prima i file esistenti
    listener.process_existing_files()
    
    # Avvia il monitoraggio in un thread separato
    def monitor():
        listener.start_monitoring()
        try:
            while listener.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            listener.stop_monitoring()
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    
    return listener


# Esempio di utilizzo
if __name__ == "__main__":
    # Mappa di rinominazione di esempio
    example_map = {
        "_01_right": "_01",
        "_01_left": "_04", 
        "_02_left": "_02",
        "_02_right": "_03",
    }
    
    # Directory di test
    test_dir = "/tmp/test_output"
    
    # Avvia il listener
    listener = start_file_listener_thread(test_dir, example_map, verbose=True)
    
    try:
        # Mantieni il programma in esecuzione
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        listener.stop_monitoring()
        print("Programma terminato.")
