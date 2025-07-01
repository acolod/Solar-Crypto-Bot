import React, { createContext, useContext, ReactNode, useEffect, useState } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { LoginPage } from './LoginPage';
import { UserDetailsPanel } from './UserDetailsPanel';
import { Client } from '@hey-api/client-fetch';
import { UserDetails } from '../types/auth-types';

interface AuthContextType {
    isLoggedIn: boolean;
    userDetails: UserDetails | null;
    authLoading: boolean;
    token: string | null;
    logout: () => void;
    login: () => void;
    clientReady: boolean;
    appName?: string;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuthContext = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuthContext must be used within an AuthProvider');
    }
    return context;
};

export const SignedIn: React.FC<{ children: ReactNode }> = ({ children }) => {
    const { isLoggedIn, clientReady, token } = useAuthContext();
    
    if (!clientReady || !isLoggedIn || !token) {
        return null;
    }
    
    return <>{children}</>;
};

export const SignedOut: React.FC<{ children?: ReactNode }> = ({ children }) => {
    const { isLoggedIn, clientReady } = useAuthContext();
    
    if (!clientReady) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
                <div className="animate-spin rounded-full h-8 w-8 border-4 border-t-transparent"></div>
                <p className="ml-2 text-gray-600">Authenticating...</p>
            </div>
        );
    }
    
    if (isLoggedIn) {
        return null;
    }
    
    return <>{children}</>;
};

interface AuthProviderProps {
    children: ReactNode;
    client: Client;
    baseInfranodeUrl: string;
    clientId: string;
    loginRedirectUrl?: string;
    appName?: string;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, client, baseInfranodeUrl, loginRedirectUrl, clientId, appName }) => {
    const [authToken, setAuthToken] = useState<string | null>(null);
    const baseUrl = "https://" + window.location.hostname.replace("5173", "8000");
    const {
        isLoggedIn,
        userDetails,
        authLoading,
        login,
        logout,
        token
    } = useAuth(baseUrl, baseInfranodeUrl, loginRedirectUrl, clientId);

    useEffect(() => {
        if (isLoggedIn && token) {
            const interceptor = client.interceptors.request.use((request) => {
                request.headers.set("Authorization", `Bearer ${token}`);
                return request;
            });
            
            setAuthToken(token);
            
            return () => {
                client.interceptors.request.eject(interceptor);
            };
        }
    }, [isLoggedIn, token, client]);

    const clientReady = !authLoading && (isLoggedIn ? !!token : true);

    return (
        <AuthContext.Provider value={{ isLoggedIn, userDetails, authLoading, token: authToken, logout, login, clientReady, appName }}>
            {children}
            
        </AuthContext.Provider>
    );
};