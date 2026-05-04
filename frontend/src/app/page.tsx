'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { isAuthenticated } from '@/lib/api';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated()) {
      router.replace('/dashboard');
    } else {
      router.replace('/login');
    }
  }, [router]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--sa-abyss)',
    }}>
      <div style={{
        width: 32,
        height: 32,
        border: '2px solid rgba(201, 168, 76, 0.2)',
        borderTopColor: 'var(--sa-gold)',
        borderRadius: '50%',
        animation: 'sa-spin 0.8s linear infinite',
      }} />
    </div>
  );
}
