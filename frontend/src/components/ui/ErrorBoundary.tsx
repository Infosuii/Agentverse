import React from 'react';
import { InlineError } from './primitives';

export interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallbackTitle?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="p-4">
          <InlineError
            title={this.props.fallbackTitle ?? 'Something went wrong rendering this view'}
            message={this.state.error.message || 'Unexpected UI error'}
            onRetry={this.handleReset}
          />
        </div>
      );
    }
    return this.props.children;
  }
}
