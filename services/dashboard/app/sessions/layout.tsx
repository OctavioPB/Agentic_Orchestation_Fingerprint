import Footer from '@/components/ui/Footer';
import NavBar from '@/components/ui/NavBar';

/** Shared layout for all /sessions/* routes — nav + footer shell. */
export default function SessionsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <NavBar />
      <main style={{ flex: 1 }}>{children}</main>
      <Footer />
    </div>
  );
}
