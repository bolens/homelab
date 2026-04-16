import React from 'react';
import { cx } from './cx';

type CheckboxProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> & {
  label: React.ReactNode;
  hint?: React.ReactNode;
  containerClassName?: string;
};

const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, hint, className, containerClassName, id, ...props },
  ref,
) {
  return (
    <label htmlFor={id} className={cx('ui-checkbox', containerClassName)}>
      <input ref={ref} id={id} type='checkbox' className={cx('ui-checkbox__input', className)} {...props} />
      <span className='ui-checkbox__text'>
        <span className='ui-checkbox__label'>{label}</span>
        {hint ? <span className='ui-checkbox__hint'>{hint}</span> : null}
      </span>
    </label>
  );
});

export default Checkbox;
