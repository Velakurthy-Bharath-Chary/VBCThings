import { createContext, useContext } from 'react';

export const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

// FILE PURPOSE:
// Shares the React authentication context and hook without mixing
// component exports into the provider module.
