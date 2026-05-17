import { redirect } from 'next/navigation';

/** Root route: redirect authenticated users to sessions, others to login. */
export default function Home() {
  redirect('/sessions');
}
