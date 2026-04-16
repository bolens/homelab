import React from 'react';
import { cx } from './cx';

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, ...props },
  ref,
) {
  return <input ref={ref} className={cx('ui-input', className)} {...props} />;
});

export default Input;
