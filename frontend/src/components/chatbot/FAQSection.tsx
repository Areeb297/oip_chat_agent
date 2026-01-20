'use client';

import { useState } from 'react';
import { ChevronRight, ArrowLeft, FileText, HelpCircle, Send } from 'lucide-react';
import { faqCategories, type FAQCategory, type FAQQuestion } from '@/lib/faqData';
import { cn } from '@/lib/utils';

type FAQView = 'categories' | 'questions' | 'answer';

interface FAQSectionProps {
  onQuestionClick?: (question: string) => void;
  /** If true, allows content to overflow without scrolling (for full screen view) */
  noScroll?: boolean;
}

export function FAQSection({ onQuestionClick, noScroll = false }: FAQSectionProps) {
  const [view, setView] = useState<FAQView>('categories');
  const [selectedCategory, setSelectedCategory] = useState<FAQCategory | null>(null);
  const [selectedQuestion, setSelectedQuestion] = useState<FAQQuestion | null>(null);

  const handleCategoryClick = (category: FAQCategory) => {
    setSelectedCategory(category);
    setView('questions');
  };

  const handleQuestionClick = (question: FAQQuestion) => {
    setSelectedQuestion(question);
    setView('answer');
  };

  const handleBackToCategories = () => {
    setView('categories');
    setSelectedCategory(null);
    setSelectedQuestion(null);
  };

  const handleBackToQuestions = () => {
    setView('questions');
    setSelectedQuestion(null);
  };

  const handleAskQuestion = (questionText: string) => {
    if (onQuestionClick) {
      onQuestionClick(questionText);
    }
  };

  // Categories View
  if (view === 'categories') {
    return (
      <div className={cn('h-full', noScroll ? 'overflow-visible' : 'overflow-y-auto')}>
        <div className="px-4 py-3 space-y-2.5">
          {faqCategories.map((category) => (
            <button
              key={category.id}
              onClick={() => handleCategoryClick(category)}
              className={cn(
                'w-full flex items-center gap-3 p-3.5 rounded-xl',
                'bg-white border border-slate-200',
                'hover:bg-slate-50 hover:border-slate-300 hover:shadow-sm',
                'transition-all duration-200',
                'text-left group'
              )}
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
                <FileText className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800">
                  {category.title}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {category.questions.length} question{category.questions.length !== 1 ? 's' : ''}
                </p>
              </div>
              <ChevronRight className="h-5 w-5 text-slate-400 group-hover:text-slate-600 transition-colors" />
            </button>
          ))}
        </div>
      </div>
    );
  }

  // Questions View
  if (view === 'questions' && selectedCategory) {
    return (
      <div className="h-full flex flex-col">
        {/* Back button */}
        <button
          onClick={handleBackToCategories}
          className="flex items-center gap-1.5 px-4 py-2.5 text-sm text-blue-600 hover:text-blue-700 transition-colors shrink-0"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Categories</span>
        </button>

        {/* Category header */}
        <div className="px-4 pb-3 border-b border-slate-100 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-800">
                {selectedCategory.title}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {selectedCategory.description}
              </p>
            </div>
          </div>
        </div>

        {/* Questions list - scrollable */}
        <div className={cn('flex-1', noScroll ? 'overflow-visible' : 'overflow-y-auto')}>
          <div className="px-4 py-3 space-y-2.5">
            {selectedCategory.questions.map((question) => (
              <button
                key={question.id}
                onClick={() => handleQuestionClick(question)}
                className={cn(
                  'w-full flex items-start gap-3 p-3.5 rounded-xl',
                  'bg-white border border-slate-200',
                  'hover:bg-slate-50 hover:border-slate-300 hover:shadow-sm',
                  'transition-all duration-200',
                  'text-left group'
                )}
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500 mt-0.5">
                  <HelpCircle className="h-4 w-4" />
                </div>
                <p className="text-sm text-slate-700 leading-relaxed flex-1">
                  {question.question}
                </p>
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Answer View
  if (view === 'answer' && selectedQuestion) {
    return (
      <div className="h-full flex flex-col">
        {/* Back button */}
        <button
          onClick={handleBackToQuestions}
          className="flex items-center gap-1.5 px-4 py-2.5 text-sm text-blue-600 hover:text-blue-700 transition-colors shrink-0"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back</span>
        </button>

        {/* Question and Answer - scrollable */}
        <div className={cn('flex-1', noScroll ? 'overflow-visible' : 'overflow-y-auto')}>
          <div className="px-4 pb-6">
            <h3 className="text-sm font-semibold text-slate-800 mb-3 leading-snug">
              {selectedQuestion.question}
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed">
              {selectedQuestion.answer}
            </p>

            {/* Ask this question button - smaller, not full width */}
            <div className="mt-5 flex justify-center">
              <button
                onClick={() => handleAskQuestion(selectedQuestion.question)}
                className={cn(
                  'inline-flex items-center gap-2 py-2 px-5 rounded-full',
                  'bg-blue-600 text-white text-sm font-medium',
                  'hover:bg-blue-700 transition-colors shadow-sm'
                )}
              >
                <Send className="h-3.5 w-3.5" />
                Ask this question
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
