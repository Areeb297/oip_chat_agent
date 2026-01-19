'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ChatWidget } from '@/components/chatbot';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { MessageCircle, BarChart3, Clock, LogOut, User } from 'lucide-react';
import { useUser } from '@/contexts/UserContext';

export default function Home() {
  const { isLoggedIn, username, roleName, logout } = useUser();
  const router = useRouter();

  // Redirect to login if not logged in
  useEffect(() => {
    if (!isLoggedIn) {
      router.push('/login');
    }
  }, [isLoggedIn, router]);

  // Show nothing while checking login status
  if (!isLoggedIn) {
    return null;
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-white">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur-sm">
        <div className="container mx-auto flex items-center justify-between px-4 py-3">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <svg
              className="h-8 w-8"
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
            <span className="text-lg font-bold text-[#1e3a5f]">Ebttikar-OIP</span>
          </div>

          {/* User Info & Logout */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 rounded-lg bg-slate-100 px-3 py-2">
              <User className="h-4 w-4 text-slate-500" />
              <span className="text-sm font-medium text-[#1e3a5f]">{username}</span>
              {roleName && (
                <>
                  <span className="text-slate-300">|</span>
                  <span className="text-sm font-medium text-[#3b82f6]">{roleName}</span>
                </>
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              className="text-slate-500 hover:text-red-500 hover:bg-red-50"
            >
              <LogOut className="mr-1 h-4 w-4" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="flex flex-col items-center text-center">
          {/* Logo - Light version matching OIP */}
          <div className="mb-8 flex items-center gap-3">
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
            <div className="text-left">
              <span className="text-2xl font-bold text-[#1e3a5f]">
                Ebttikar-OIP
              </span>
              <p className="text-xs text-[#3b82f6]">Operational & Intelligence Platform</p>
            </div>
          </div>

          {/* Heading */}
          <p className="mb-2 text-sm font-semibold text-[#3b82f6] tracking-wide">
            Unified Ticketing System
          </p>
          <h1 className="mb-4 text-4xl font-bold text-[#1e3a5f] md:text-5xl">
            <span className="text-[#3b82f6]">Effortlessly manage</span>
            <br />
            your team and operations
          </h1>
          <p className="mb-8 max-w-xl text-base text-slate-500">
            Real-time monitoring, SLA tracking, and predictive analytics.
          </p>

          {/* CTA Buttons */}
          <div className="flex gap-4">
            <Button asChild size="lg" className="bg-[#3b82f6] hover:bg-[#2563eb]">
              <Link href="/chat">
                Open Full Chat
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <a href="#features">
                Learn More
              </a>
            </Button>
          </div>
        </div>

        {/* Feature Cards */}
        <div id="features" className="mt-24 grid gap-6 md:grid-cols-3">
          <Card className="border-slate-200 shadow-sm transition-all hover:shadow-md hover:border-[#3b82f6]/30">
            <CardContent className="p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-blue-50">
                <MessageCircle className="h-6 w-6 text-[#3b82f6]" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-[#1e3a5f]">AI-Powered Chat</h3>
              <p className="text-sm text-slate-500">
                Get instant answers about tickets, SLAs, inventory, and platform
                features using our intelligent assistant.
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm transition-all hover:shadow-md hover:border-[#22c55e]/30">
            <CardContent className="p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-green-50">
                <BarChart3 className="h-6 w-6 text-[#22c55e]" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-[#1e3a5f]">Real-time Analytics</h3>
              <p className="text-sm text-slate-500">
                Monitor ticket distribution, SLA compliance, and resource
                performance with live dashboards.
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm transition-all hover:shadow-md hover:border-[#f97316]/30">
            <CardContent className="p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-orange-50">
                <Clock className="h-6 w-6 text-[#f97316]" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-[#1e3a5f]">SLA Management</h3>
              <p className="text-sm text-slate-500">
                Track service level agreements with automated alerts and
                compliance reporting.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Stats Section */}
        <Card className="mt-16 border-slate-200 shadow-sm">
          <CardContent className="p-8">
            <div className="grid gap-8 text-center md:grid-cols-4">
              <div>
                <div className="text-3xl font-bold text-[#3b82f6]">38</div>
                <div className="mt-1 text-sm text-slate-500">Total Tickets</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-[#f97316]">23</div>
                <div className="mt-1 text-sm text-slate-500">Open</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-[#22c55e]">9</div>
                <div className="mt-1 text-sm text-slate-500">Closed</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-[#eab308]">1</div>
                <div className="mt-1 text-sm text-slate-500">Pending</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Instructions */}
        <div className="mt-16 text-center">
          <p className="text-sm text-slate-400">
            Click the chat icon in the bottom-right corner to start a
            conversation with the OIP Assistant.
          </p>
        </div>

        {/* Footer */}
        <div className="mt-16 text-center border-t pt-8">
          <p className="text-xs text-slate-400">
            Powered by <span className="text-[#3b82f6]">Ebttikar</span>
          </p>
          <p className="text-xs text-slate-400">
            © 2026 Ebttikar Technology. All Rights Reserved.
          </p>
        </div>
      </div>

      {/* Floating Chat Widget */}
      <ChatWidget position="bottom-right" />
    </main>
  );
}
