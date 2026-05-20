import NavBar from '@/components/ui/NavBar';
import Footer from '@/components/ui/Footer';

export default function ScenariosLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <NavBar />
      <main style={{ flex: 1 }}>{children}</main>
      <Footer />
    </div>
  );
}
