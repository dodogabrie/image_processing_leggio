import electron from 'electron';
import util from 'util';

// Determine application name safely (zip_worker might run outside Electron)
const appName = (electron && electron.app && electron.app.name) || process.title || 'app';

/**
 * Logger utility: logs messages with timestamp, level, and optional context.
 */
export default class Logger {
  /**
   * @param {string} [context] - Optional context for log messages.
   */
  constructor(context = '') {
    this.context = context;
  }

  /**
   * Internal formatting of log messages.
   * @private
   */
  _format(level, ...args) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${appName}] [${level}]${this.context ? ` [${this.context}]` : ''}`;
    const message = args.map(arg => (typeof arg === 'string' ? arg : util.inspect(arg))).join(' ');
    return `${prefix} ${message}`;
  }

  info(...args) {
    console.log(this._format('INFO', ...args));
  }

  warn(...args) {
    console.warn(this._format('WARN', ...args));
  }

  error(...args) {
    console.error(this._format('ERROR', ...args));
  }

  debug(...args) {
    console.debug(this._format('DEBUG', ...args));
  }
}
