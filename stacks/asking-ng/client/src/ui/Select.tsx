import React from 'react';
import { cx } from './cx';

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement>;

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, children, ...props },
  ref,
) {
  return (
    <select ref={ref} className={cx('ui-input', 'ui-select', className)} {...props}>
      {children}
    </select>
  );
});

export default Select;
