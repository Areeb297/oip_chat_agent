'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUser } from '@/contexts/UserContext';
import { USERS, getUserByUsername } from '@/lib/constants';

export default function LoginPage() {
  const [selectedUser, setSelectedUser] = useState<string>('');
  const { login, isLoggedIn } = useUser();
  const router = useRouter();

  // Get the selected user's details
  const selectedUserDetails = useMemo(() => {
    if (!selectedUser) return null;
    return getUserByUsername(selectedUser);
  }, [selectedUser]);

  // Redirect if already logged in
  useEffect(() => {
    if (isLoggedIn) {
      router.push('/');
    }
  }, [isLoggedIn, router]);

  const handleContinue = () => {
    if (selectedUser) {
      login(selectedUser);
      router.push('/');
    }
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-white flex items-center justify-center p-4">
      <Card className="w-full max-w-md border-slate-200 shadow-lg">
        <CardHeader className="text-center space-y-4">
          {/* Logo */}
          <div className="flex justify-center">
            <div className="flex items-center gap-3">
              <svg
                className="h-12 w-12"
                viewBox="0 0 48 48"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M24 4L4 14L24 24L44 14L24 4Z"
                  fill="#3b82f6"
                  fillOpacity="0.2"
                  stroke="#3b82f6"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M4 34L24 44L44 34"
                  stroke="#1e3a5f"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M4 24L24 34L44 24"
                  stroke="#3b82f6"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          </div>
          <div>
            <CardTitle className="text-2xl font-bold text-[#1e3a5f]">
              Ebttikar-OIP
            </CardTitle>
            <CardDescription className="text-[#3b82f6]">
              Operational & Intelligence Platform
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-700">
              Select User
            </label>
            <Select value={selectedUser} onValueChange={setSelectedUser}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a user to continue..." />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {USERS.map((user) => (
                  <SelectItem key={user.username} value={user.username}>
                    <div className="flex items-center justify-between w-full gap-2">
                      <span>{user.username}</span>
                      <span className="text-xs text-slate-400">({user.roleName})</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-slate-400">
              This is a testing interface - no password required
            </p>
          </div>

          {/* Show selected user's role */}
          {selectedUserDetails && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="flex items-center gap-2 text-sm">
                <Shield className="h-4 w-4 text-[#3b82f6]" />
                <span className="text-slate-600">Role:</span>
                <span className="font-medium text-[#1e3a5f]">{selectedUserDetails.roleName}</span>
              </div>
              <div className="text-xs text-slate-400 mt-1 ml-6">
                {selectedUserDetails.email}
              </div>
            </div>
          )}

          <Button
            onClick={handleContinue}
            disabled={!selectedUser}
            className="w-full bg-[#3b82f6] hover:bg-[#2563eb]"
          >
            Continue
          </Button>

          <p className="text-xs text-center text-slate-400">
            Select a user to access the OIP Assistant
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
