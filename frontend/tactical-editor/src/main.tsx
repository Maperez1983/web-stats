import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import './styles.css';

const rootNode = document.getElementById('tactical-editor-root');

if (rootNode) {
  const documentUrl = rootNode.getAttribute('data-document-url') || '';
  ReactDOM.createRoot(rootNode).render(
    <React.StrictMode>
      <App documentUrl={documentUrl} />
    </React.StrictMode>
  );
}
