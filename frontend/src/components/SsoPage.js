import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';

const SsoPage = () => {
  const location = useLocation();
  const [error, setError] = useState('');

  useEffect(() => {
    const run = async () => {
      const params = new URLSearchParams(location.search);
      const code = (params.get('code') || '').trim();
      const redirectParam = (params.get('redirect') || '').trim();

      const allowedRedirectPaths = new Set(['/subscribe']);
      const redirectPath = allowedRedirectPaths.has(redirectParam) ? redirectParam : '/subscribe';

      if (!code) {
        setError('Missing code');
        return;
      }

      try {
        const resp = await axios.post('/api/sso/exchange', { code });
        const accessToken = resp?.data?.access_token;

        if (!accessToken) {
          setError('Missing token');
          return;
        }

        const tokenPayload = JSON.parse(atob(accessToken.split('.')[1]));
        const role = tokenPayload.role || 'admin';

        sessionStorage.setItem('authToken', accessToken);
        sessionStorage.setItem('userRole', role);
        localStorage.removeItem('authToken');
        localStorage.removeItem('userRole');

        window.location.href = redirectPath;
      } catch (e) {
        setError(e?.response?.data?.detail || e?.message || 'SSO failed');
      }
    };

    run();
  }, [location.search]);

  return (
    <div className="min-h-screen bg-white flex items-center justify-center px-4" style={{ fontFamily: 'Inter, sans-serif' }}>
      <div className="w-full max-w-md text-center">
        {error ? (
          <div className="text-sm text-red-600 font-semibold">{error}</div>
        ) : (
          <div className="text-sm text-gray-600 font-semibold">Redirecting...</div>
        )}
      </div>
    </div>
  );
};

export default SsoPage;
