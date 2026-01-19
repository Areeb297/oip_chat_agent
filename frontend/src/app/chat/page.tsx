import { Suspense } from 'react';
import { ChatFullScreen } from '@/components/chatbot';

export const metadata = {
  title: 'OIP Assistant - Chat',
  description: 'Chat with the OIP Assistant for help with tickets, SLAs, and more.',
};

function ChatPageContent() {
  return <ChatFullScreen />;
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center">Loading...</div>}>
      <ChatPageContent />
    </Suspense>
  );
}
