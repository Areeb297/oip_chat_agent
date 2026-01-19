'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { getUserByUsername, type User } from '@/lib/constants';

interface UserContextType {
  username: string | null;
  email: string | null;
  roleId: number | null;
  roleName: string | null;
  roleCode: string | null;
  projectCode: string | null;
  team: string | null;
  isLoggedIn: boolean;
  isLoaded: boolean;
  login: (username: string) => void;
  logout: () => void;
  setProject: (projectCode: string | null) => void;
  setTeam: (team: string | null) => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

const STORAGE_KEY = 'oip_user_context';

interface StoredUserContext {
  username: string | null;
  email: string | null;
  roleId: number | null;
  roleName: string | null;
  roleCode: string | null;
  projectCode: string | null;
  team: string | null;
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [roleId, setRoleId] = useState<number | null>(null);
  const [roleName, setRoleName] = useState<string | null>(null);
  const [roleCode, setRoleCode] = useState<string | null>(null);
  const [projectCode, setProjectCode] = useState<string | null>(null);
  const [team, setTeam] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const data: StoredUserContext = JSON.parse(stored);
        setUsername(data.username);
        setEmail(data.email);
        setRoleId(data.roleId);
        setRoleName(data.roleName);
        setRoleCode(data.roleCode);
        setProjectCode(data.projectCode);
        setTeam(data.team);
      }
    } catch (e) {
      console.error('Failed to load user context from localStorage:', e);
    }
    setIsLoaded(true);
  }, []);

  // Save to localStorage when values change
  useEffect(() => {
    if (!isLoaded) return;

    const data: StoredUserContext = {
      username,
      email,
      roleId,
      roleName,
      roleCode,
      projectCode,
      team
    };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.error('Failed to save user context to localStorage:', e);
    }
  }, [username, email, roleId, roleName, roleCode, projectCode, team, isLoaded]);

  const login = (newUsername: string) => {
    // Look up user info from constants
    const user = getUserByUsername(newUsername);
    if (user) {
      setUsername(user.username);
      setEmail(user.email);
      setRoleId(user.roleId);
      setRoleName(user.roleName);
      setRoleCode(user.roleCode);
    } else {
      // Fallback for unknown users
      setUsername(newUsername);
      setEmail(null);
      setRoleId(null);
      setRoleName(null);
      setRoleCode(null);
    }
  };

  const logout = () => {
    setUsername(null);
    setEmail(null);
    setRoleId(null);
    setRoleName(null);
    setRoleCode(null);
    setProjectCode(null);
    setTeam(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.error('Failed to remove user context from localStorage:', e);
    }
  };

  const handleSetProject = (code: string | null) => {
    setProjectCode(code);
  };

  const handleSetTeam = (newTeam: string | null) => {
    setTeam(newTeam);
  };

  const isLoggedIn = username !== null;

  return (
    <UserContext.Provider
      value={{
        username,
        email,
        roleId,
        roleName,
        roleCode,
        projectCode,
        team,
        isLoggedIn,
        isLoaded,
        login,
        logout,
        setProject: handleSetProject,
        setTeam: handleSetTeam,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
}
