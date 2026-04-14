import Navbar from 'react-bootstrap/Navbar';
import Nav from 'react-bootstrap/Nav';
import useWindowDimensions from '../helpers/useWindowDimensions';

export default function NavbarWrapper() {
  const { width } = useWindowDimensions();
  return (
    <Navbar className={width > 500 ? 'navbar-main' : 'navbar-main-mobile'}>
      <Navbar.Brand href='/' className='navbar-brand'>
        {import.meta.env.VITE_APP_NAME || 'asking.one'}
      </Navbar.Brand>
      <Navbar.Toggle />
      <Navbar.Collapse className='justify-content-end navbar-links'>
        <Nav.Link href='https://github.com/jdleo/asking' target='_blank' className='navbar-link'>
          Github
        </Nav.Link>
      </Navbar.Collapse>
    </Navbar>
  );
}
