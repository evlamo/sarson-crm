import type { HelpArticle } from '@/lib/help-articles';
import { useState, useMemo } from 'react';
import { useLocation } from '@tanstack/react-router';
import { Search, ChevronLeft, ChevronRight, BookOpen, FileText } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { helpArticles, categories, getArticlesByCategory, searchArticles, getContextualArticles } from '@/lib/help-articles';
import { cn } from '@/lib/utils';


interface HelpPanelProps {
  onClose: () => void;
}

type View = 'home' | 'category' | 'article' | 'search';

export default function HelpPanel({ onClose }: HelpPanelProps) {
  const location = useLocation();
  const [view, setView] = useState<View>('home');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<HelpArticle | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const contextualArticles = useMemo(
    () => getContextualArticles(location.pathname),
    [location.pathname]
  );

  const searchResults = useMemo(
    () => searchArticles(searchQuery),
    [searchQuery]
  );

  const categoryArticles = useMemo(
    () => (selectedCategory ? getArticlesByCategory(selectedCategory) : []),
    [selectedCategory]
  );

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (q.length > 0) {
      setView('search');
    } else if (view === 'search') {
      setView('home');
    }
  };

  const openCategory = (category: string) => {
    setSelectedCategory(category);
    setView('category');
  };

  const openArticle = (article: HelpArticle) => {
    setSelectedArticle(article);
    setView('article');
  };

  const goBack = () => {
    if (view === 'article') {
      if (selectedCategory) {
        setView('category');
      } else {
        setView(searchQuery ? 'search' : 'home');
      }
      setSelectedArticle(null);
    } else if (view === 'category') {
      setView('home');
      setSelectedCategory(null);
    } else if (view === 'search') {
      setSearchQuery('');
      setView('home');
    }
  };

  const renderMarkdown = (content: string) => {
    // Simple markdown rendering
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let inList = false;
    let listItems: string[] = [];

    const flushList = () => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`list-${elements.length}`} className="list-disc pl-5 my-2 space-y-1">
            {listItems.map((item, i) => (
              <li key={i} className="text-sm text-muted-foreground">{item}</li>
            ))}
          </ul>
        );
        listItems = [];
        inList = false;
      }
    };

    lines.forEach((line, idx) => {
      // Headers
      if (line.startsWith('# ')) {
        flushList();
        elements.push(
          <h1 key={idx} className="text-lg font-semibold text-foreground mb-2">
            {line.slice(2)}
          </h1>
        );
      } else if (line.startsWith('## ')) {
        flushList();
        elements.push(
          <h2 key={idx} className="text-base font-semibold text-foreground mt-4 mb-2">
            {line.slice(3)}
          </h2>
        );
      } else if (line.startsWith('### ')) {
        flushList();
        elements.push(
          <h3 key={idx} className="text-sm font-semibold text-foreground mt-3 mb-1">
            {line.slice(4)}
          </h3>
        );
      }
      // List items
      else if (line.startsWith('- ')) {
        inList = true;
        listItems.push(formatInlineMarkdown(line.slice(2)));
      } else if (/^\d+\. /.test(line)) {
        inList = true;
        listItems.push(formatInlineMarkdown(line.replace(/^\d+\. /, '')));
      }
      // Tables (simplified)
      else if (line.startsWith('|')) {
        flushList();
        // Skip table for now, just show text
      }
      // Empty line
      else if (line.trim() === '') {
        flushList();
      }
      // Regular paragraph
      else {
        flushList();
        elements.push(
          <p key={idx} className="text-sm text-muted-foreground my-2">
            {formatInlineMarkdown(line)}
          </p>
        );
      }
    });

    flushList();
    return elements;
  };

  const formatInlineMarkdown = (text: string): React.ReactNode => {
    // Handle **bold**, `code`, and links
    const parts: React.ReactNode[] = [];
    let remaining = text;
    let key = 0;

    while (remaining.length > 0) {
      // Bold
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
      // Code
      const codeMatch = remaining.match(/`(.+?)`/);

      if (boldMatch && (!codeMatch || boldMatch.index! <= codeMatch.index!)) {
        const before = remaining.slice(0, boldMatch.index);
        if (before) parts.push(before);
        parts.push(
          <strong key={key++} className="font-semibold text-foreground">
            {boldMatch[1]}
          </strong>
        );
        remaining = remaining.slice(boldMatch.index! + boldMatch[0].length);
      } else if (codeMatch) {
        const before = remaining.slice(0, codeMatch.index);
        if (before) parts.push(before);
        parts.push(
          <code
            key={key++}
            className="px-1 py-0.5 bg-muted rounded text-xs font-mono"
          >
            {codeMatch[1]}
          </code>
        );
        remaining = remaining.slice(codeMatch.index! + codeMatch[0].length);
      } else {
        parts.push(remaining);
        break;
      }
    }

    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center gap-2 mb-3">
          {view !== 'home' && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={goBack}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          )}
          <h2 className="font-semibold text-foreground">
            {view === 'home' && 'Help Center'}
            {view === 'category' && selectedCategory}
            {view === 'article' && 'Article'}
            {view === 'search' && 'Search Results'}
          </h2>
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search help articles..."
            value={searchQuery}
            onChange={handleSearch}
            className="pl-9"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {/* Home View */}
        {view === 'home' && (
          <div className="space-y-6">
            {/* Contextual Help */}
            {contextualArticles.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2 flex items-center gap-2">
                  <BookOpen className="h-4 w-4 text-[#253a52]" />
                  Help for this page
                </h3>
                <div className="space-y-1">
                  {contextualArticles.map((article) => (
                    <button
                      key={article.id}
                      onClick={() => openArticle(article)}
                      className="w-full text-left p-2 rounded hover:bg-muted transition-colors"
                    >
                      <p className="text-sm font-medium text-foreground">
                        {article.title}
                      </p>
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {article.category}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Categories */}
            <div>
              <h3 className="text-sm font-medium text-foreground mb-2">
                Browse Topics
              </h3>
              <div className="space-y-1">
                {categories.map((category) => (
                  <button
                    key={category}
                    onClick={() => openCategory(category)}
                    className={cn(
                      'w-full flex items-center justify-between p-2 rounded',
                      'hover:bg-muted transition-colors text-left'
                    )}
                  >
                    <span className="text-sm text-foreground">{category}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Category View */}
        {view === 'category' && selectedCategory && (
          <div className="space-y-1">
            {categoryArticles.map((article) => (
              <button
                key={article.id}
                onClick={() => openArticle(article)}
                className="w-full text-left p-3 rounded hover:bg-muted transition-colors"
              >
                <div className="flex items-start gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {article.title}
                    </p>
                    <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
                      {article.content.split('\n')[0].replace(/^#+ /, '')}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Search Results */}
        {view === 'search' && (
          <div>
            {searchResults.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No articles found for "{searchQuery}"
              </p>
            ) : (
              <div className="space-y-1">
                {searchResults.map((article) => (
                  <button
                    key={article.id}
                    onClick={() => openArticle(article)}
                    className="w-full text-left p-3 rounded hover:bg-muted transition-colors"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {article.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {article.category}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Article View */}
        {view === 'article' && selectedArticle && (
          <div className="prose prose-sm max-w-none">
            {renderMarkdown(selectedArticle.content)}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t text-center">
        <p className="text-xs text-muted-foreground">
          Press <kbd className="px-1.5 py-0.5 bg-muted rounded text-xs">?</kbd> to toggle help
        </p>
      </div>
    </div>
  );
}
