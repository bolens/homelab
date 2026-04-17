import React from 'react';
import { cx } from './cx';

type FieldProps = React.HTMLAttributes<HTMLDivElement> & {
  label?: string;
  htmlFor?: string;
  hint?: string;
  error?: string;
};

export default function Field({
  label,
  htmlFor,
  hint,
  error,
  className,
  children,
  ...props
}: FieldProps) {
  const generatedId = React.useId().replace(/:/g, '');
  const controlId = htmlFor ?? `ui-field-control-${generatedId}`;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;

  let renderedChildren = children;
  if (React.isValidElement(children)) {
    const childProps = (children.props ?? {}) as Record<string, unknown>;
    const describedByParts: string[] = [];
    const existingDescribedBy =
      typeof childProps['aria-describedby'] === 'string' ? childProps['aria-describedby'] : '';
    if (existingDescribedBy.trim()) describedByParts.push(existingDescribedBy.trim());
    if (hintId) describedByParts.push(hintId);
    if (errorId) describedByParts.push(errorId);
    const ariaDescribedBy = describedByParts.length > 0 ? describedByParts.join(' ') : undefined;
    const nextProps: Record<string, unknown> = {};
    if (label && childProps['id'] == null) nextProps['id'] = controlId;
    if (ariaDescribedBy) nextProps['aria-describedby'] = ariaDescribedBy;
    if (error && childProps['aria-invalid'] == null) nextProps['aria-invalid'] = true;
    renderedChildren = React.cloneElement(children, nextProps);
  }

  return (
    <div className={cx('ui-field', className)} {...props}>
      {label ? (
        <label htmlFor={controlId} className='ui-field__label'>
          {label}
        </label>
      ) : null}
      {renderedChildren}
      {hint ? (
        <p id={hintId} className='ui-field__hint'>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className='ui-field__error' role='alert'>
          {error}
        </p>
      ) : null}
    </div>
  );
}
