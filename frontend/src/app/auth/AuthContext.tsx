/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { Amplify } from 'aws-amplify';
import { getCurrentUser, signOut as amplifySignOut, signInWithRedirect } from 'aws-amplify/auth';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  userId: string | null;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const isMock = import.meta.env.VITE_USE_MOCK_API !== 'false';

if (!isMock) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || '',
        userPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID || '',
        loginWith: {
          oauth: {
            domain: import.meta.env.VITE_COGNITO_DOMAIN || '',
            scopes: ['email', 'openid', 'profile'],
            redirectSignIn: [window.location.origin],
            redirectSignOut: [window.location.origin],
            responseType: 'code'
          }
        }
      }
    }
  });
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const checkUser = async () => {
      try {
        const user = await getCurrentUser();
        setIsAuthenticated(true);
        setUserId(user.userId);
      } catch {
        setIsAuthenticated(false);
        setUserId(null);
      } finally {
        setIsLoading(false);
      }
    };

    if (isMock) {
      // Check mock session
      const mockSession = localStorage.getItem('mock_auth');
      if (mockSession) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setIsAuthenticated(true);
        setUserId('mock_user_123');
      }
      setIsLoading(false);
    } else {
      // Real Cognito check
      checkUser();
    }
  }, []);

  const login = () => {
    if (isMock) {
      localStorage.setItem('mock_auth', 'true');
      setIsAuthenticated(true);
      setUserId('mock_user_123');
      window.location.href = '/';
    } else {
      signInWithRedirect();
    }
  };

  const logout = async () => {
    if (isMock) {
      localStorage.removeItem('mock_auth');
      setIsAuthenticated(false);
      setUserId(null);
      window.location.href = '/auth';
    } else {
      try {
        await amplifySignOut();
      } catch (err) {
        console.error('Error signing out', err);
      }
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, userId, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
