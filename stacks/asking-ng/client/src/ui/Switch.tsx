import React from 'react';
import { cx } from './cx';

type SwitchProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'role'>;

const Switch = React.forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { className, disabled, ...props },
  ref,
) {
  return (
    <span className={cx('ui-switch', className)}>
      <input
        ref={ref}
        type='checkbox'
        role='switch'
        className='ui-switch__input'
        disabled={disabled}
        {...props}
      />
      <span className='ui-switch__track' aria-hidden />
    </span>
  );
});

export default Switch;
