import fsSync from 'fs';
import os from 'os';
import path from 'path';               
import util from 'util';

// Determine application name safely 
const appName = process.title || 'app';

// Funzione per determinare il path del log
function getDefaultLogPath() {
  // Se siamo in un worker o processo senza Electron
  if (!process.versions?.electron) {
    return path.join(process.cwd(), 'logs', 'worker.log');
  }
  
  try {
    // Usa NODE_ENV per determinare se siamo in produzione
    const isProduction = process.env.NODE_ENV === 'production';
    
    if (isProduction) {
      return path.join(process.resourcesPath, 'logs', 'app.log');
    } else {
      return path.join(process.cwd(), 'logs', 'app.log');
    }
  } catch {
    return path.join(process.cwd(), 'logs', 'app.log');
  }
}

export default class Logger {
  constructor(context = '', logFilePath = null) {
    this.context = context;
    this.logFilePath = logFilePath || getDefaultLogPath();
    
    // Debug: stampa il path del log al momento della creazione
    console.log(`[Logger] Inizializzato con path: ${this.logFilePath}`);
    console.log(`[Logger] NODE_ENV: ${process.env.NODE_ENV}`);
    console.log(`[Logger] process.versions.electron: ${process.versions?.electron}`);
  }

  _format(level, ...args) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${appName}] [${level}]${this.context ? ` [${this.context}]` : ''}`;
    const message = args.map(arg => (typeof arg === 'string' ? arg : util.inspect(arg))).join(' ');
    return `${prefix} ${message}`;
  }

  _writeToFile(msg) {
    // Temporaneamente disabilitato per debug
    return;
    
    if (!this.logFilePath) {
      console.log('[Logger] SKIPPING: no logFilePath');
      return;
    }
    
    console.log(`[Logger] Writing to: ${this.logFilePath}`);
    
    // Creo la cartella se non esiste
    const dir = path.dirname(this.logFilePath);
    console.log(`[Logger] Creating dir: ${dir}`);
    
    try {
      fsSync.mkdirSync(dir, { recursive: true });
      console.log(`[Logger] Dir created successfully: ${dir}`);
    } catch (err) {
      console.error(`Logger mkdirSync error:`, err);
    }
    
    // Appendo (il file viene creato se non esiste)
    try {
      fsSync.appendFileSync(this.logFilePath, msg + os.EOL, 'utf-8');
      console.log(`[Logger] File written successfully`);
    } catch (err) {
      console.error(`Failed to write log to file: ${this.logFilePath}`, err);
    }
  }

  info(...args) {
    const msg = this._format('INFO', ...args);
    console.log(msg);
    this._writeToFile(msg);
  }

  warn(...args) {
    const msg = this._format('WARN', ...args);
    console.warn(msg);
    this._writeToFile(msg);
  }

  error(...args) {
    const msg = this._format('ERROR', ...args);
    console.error(msg);
    this._writeToFile(msg);
  }

  debug(...args) {
    const msg = this._format('DEBUG', ...args);
    console.debug(msg);
    this._writeToFile(msg);
  }
}
