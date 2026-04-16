import { AppError } from './appError';

export class HttpError extends AppError {
  constructor(statusCode: number, code: string, message: string, details?: unknown) {
    super(statusCode, code, message, details);
    this.name = 'HttpError';
  }
}
