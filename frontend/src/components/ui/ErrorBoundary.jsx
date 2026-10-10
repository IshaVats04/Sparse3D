import { Component } from 'react';
import { Alert } from './Feedback';

/** Catches render errors (e.g. WebGL unavailable) and shows them instead of a blank page. */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    // eslint-disable-next-line no-console
    console.error('UI error:', error);
  }

  componentDidUpdate(prev) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback(this.state.error);
      return (
        <Alert tone="error" title={this.props.title || 'This section failed to render'}>
          {String(this.state.error.message || this.state.error)}
        </Alert>
      );
    }
    return this.props.children;
  }
}
