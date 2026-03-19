import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Noticias from './pages/Noticias';
import Historial from './pages/Historial';
import Config from './pages/Config';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [botVersion, setBotVersion] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  // Fetch version once when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    const token = localStorage.getItem('token');
    axios.get('/api/control/estado', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => setBotVersion(r.data.version || ''))
      .catch(() => {});
  }, [isAuthenticated]);

  const PrivateRoute = ({ element }) =>
    isAuthenticated ? element : <Navigate to="/login" />;

  const withVersion = (el) => React.cloneElement(el, { botVersion });

  return (
    <Router>
      <Routes>
        <Route
          path="/login"
          element={!isAuthenticated ? <Login setAuth={setIsAuthenticated} /> : <Navigate to="/control" />}
        />
        <Route path="/dashboard" element={<PrivateRoute element={withVersion(<Dashboard setAuth={setIsAuthenticated} />)} />} />
        <Route path="/control"   element={<PrivateRoute element={withVersion(<Control   setAuth={setIsAuthenticated} />)} />} />
        <Route path="/noticias"  element={<PrivateRoute element={withVersion(<Noticias  setAuth={setIsAuthenticated} />)} />} />
        <Route path="/historial" element={<PrivateRoute element={withVersion(<Historial setAuth={setIsAuthenticated} />)} />} />
        <Route path="/config"    element={<PrivateRoute element={withVersion(<Config    setAuth={setIsAuthenticated} />)} />} />
        <Route path="/" element={<Navigate to="/control" />} />
      </Routes>
    </Router>
  );
}

export default App;
