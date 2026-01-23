import fsSync from 'fs';
import os from 'os';
import path from 'path';
import util from 'util';

// Determine application name safely
const appName = process.title || 'app';

// Log directory path - will be set by main process
let logDirPath = null;

/**
 * Sets the log directory path. Should be called from main process with app.getPath('userData').
 *
 * @param {string} dir - Directory path for log files.
 */
export function setLogDirectory(dir) {
  logDirPath = dir;
  console.log(`[Logger] Log directory set to: ${logDirPath}`);
}

/**
 * Gets the current log file path.
 *
 * @returns {string|null} The log file path or null if not set.
 */
export function getLogFilePath() {
  if (!logDirPath) return null;
  return path.join(logDirPath, 'logs', 'app.log');
}

/**
 * Gets the log directory path.
 *
 * @returns {string|null} The log directory path or null if not set.
 */
export function getLogDirectory() {
  return logDirPath;
}

function getDefaultLogPath() {
  // If log directory was set by main process, use it
  if (logDirPath) {
    return path.join(logDirPath, 'logs', 'app.log');
  }

  // Fallback for workers or when not set
  if (!process.versions?.electron) {
    return path.join(process.cwd(), 'logs', 'worker.log');
  }

  // Development fallback
  return path.join(process.cwd(), 'logs', 'app.log');
}

export default class Logger {
  constructor(context = '', logFilePath = null) {
    this.context = context;
    this._explicitPath = logFilePath; // Only set if explicitly provided
  }

  _getLogPath() {
    // Always use dynamic path unless explicitly overridden
    return this._explicitPath || getDefaultLogPath();
  }

  _format(level, ...args) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${appName}] [${level}]${this.context ? ` [${this.context}]` : ''}`;
    const message = args.map(arg => (typeof arg === 'string' ? arg : util.inspect(arg))).join(' ');
    return `${prefix} ${message}`;
  }

  _writeToFile(msg) {
    const logPath = this._getLogPath();
    if (!logPath) return;

    // Create directory if needed
    const dir = path.dirname(logPath);
    try {
      fsSync.mkdirSync(dir, { recursive: true });
    } catch (err) {
      // Ignore mkdir errors (may already exist)
    }

    // Append to log file
    try {
      fsSync.appendFileSync(logPath, msg + os.EOL, 'utf-8');
    } catch (err) {
      // Silent fail - don't spam console with log write errors
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
