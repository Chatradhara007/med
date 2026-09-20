/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { Amplify } from 'aws-amplify';
import { getCurrentUser, signOut as amplifySignOut, signInWithRedirect } from 'aws-amplify/auth';
import { config, isConfigured } from '../../config';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  userId: string | null;
  /** Non-null when the last sign-in attempt failed, so the page can show it. */
  authError: string | null;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/**
 * Configuring Amplify with blank values makes it throw `Auth UserPool not
 * configured.` from inside the sign-in click handler, where nothing catches
 * it: the button appears dead and the console error is the only trace. Skip
 * configuration entirely when the app is unconfigured -- `ConfigRequired`
 * renders instead of the app, so no auth call is ever made.
 */
if (isConfigured) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        loginWith: {
          oauth: {
            domain: config.cognitoDomain,
            scopes: ['email', 'openid', 'profile'],
            redirectSignIn: [config.redirectUri],
            redirectSignOut: [config.redirectUri],
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
  const [authError, setAuthError] = useState<string | null>(null);

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

    checkUser();
  }, []);

  const login = () => {
    setAuthError(null);
    // signInWithRedirect rejects rather than throwing synchronously, so an
    // unawaited call loses the reason entirely and the button looks inert.
    signInWithRedirect().catch((err) => {
      const msg = err instanceof Error ? err.message : String(err);
      console.error('Sign-in failed', err);
      setAuthError(msg);
    });
  };

  const logout = async () => {
    try {
      await amplifySignOut();
    } catch (err) {
      console.error('Error signing out', err);
    }
    setIsAuthenticated(false);
    setUserId(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, userId, authError, login, logout }}>
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
