import {
  ConnectionError,
  DatabaseError,
  EmptyResultError,
  ForeignKeyConstraintError,
  TimeoutError,
  UniqueConstraintError,
  ValidationError,
} from 'sequelize';
import { ZodError } from 'zod';
import { AppError } from '../lib/appError';

export function errorToAppError(err: unknown): AppError {
  if (err instanceof AppError) return err;

  if (err instanceof ZodError) {
    return new AppError(400, 'VALIDATION_ERROR', 'Invalid request', err.flatten());
  }

  if (err instanceof ConnectionError) {
    return new AppError(503, 'DATABASE_UNAVAILABLE', 'Database connection failed');
  }

  if (err instanceof TimeoutError) {
    return new AppError(503, 'DATABASE_TIMEOUT', 'Database request timed out');
  }

  if (err instanceof UniqueConstraintError) {
    const message = err.errors?.map((e) => e.message).join('; ') || err.message || 'Duplicate resource';
    return new AppError(409, 'DUPLICATE_KEY', message);
  }

  if (err instanceof ForeignKeyConstraintError) {
    const message =
      err.message ||
      (err.table ? `Foreign key constraint violated (${err.table})` : 'Foreign key constraint violated');
    return new AppError(409, 'FOREIGN_KEY_VIOLATION', message);
  }

  if (err instanceof ValidationError) {
    const message = err.errors?.map((e) => e.message).join('; ') || err.message || 'Validation failed';
    return new AppError(400, 'VALIDATION_ERROR', message);
  }

  if (err instanceof EmptyResultError) {
    return new AppError(404, 'NOT_FOUND', err.message || 'Not found');
  }

  if (err instanceof DatabaseError) {
    return new AppError(500, 'DATABASE_ERROR', 'Database operation failed');
  }

  const isBodyParse = err instanceof SyntaxError && 'body' in err;
  if (isBodyParse) {
    return new AppError(400, 'INVALID_JSON', 'Malformed JSON body');
  }

  return new AppError(500, 'INTERNAL_ERROR', 'Internal server error');
}
