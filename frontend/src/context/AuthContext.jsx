import { useEffect, useState } from 'react';
import { AuthContext } from './auth-context';

import {
  getCurrentUser,
  loginUser,
} from '../services/api';

import {
  getToken,
  removeToken,
  saveToken,
} from '../services/auth';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(getToken()));

  useEffect(() => {
    const token = getToken();

    if (!token) {
      return;
    }

    getCurrentUser(token)
      .then((currentUser) => {
        setUser(currentUser);
      })
      .catch(() => {
        removeToken();
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  async function login(email, password) {
    const data = await loginUser(email, password);

    saveToken(data.access_token);

    const currentUser = await getCurrentUser(data.access_token);
    setUser(currentUser);
  }

  function logout() {
    removeToken();
    setUser(null);
  }

  const value = {
    user,
    loading,
    isAuthenticated: Boolean(user),
    login,
    logout,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

// FILE PURPOSE:
// Provides global authentication state, JWT session handling,
// login, logout, and authenticated-user loading for the React application.
