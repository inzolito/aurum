import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Noticias from './pages/Noticias';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const PrivateRoute = ({ element }) =>
    isAuthenticated ? element : <Navigate to="/login" />;

  return (
    <Router>
      <Routes>
        <Route
          path="/login"
          element={!isAuthenticated ? <Login setAuth={setIsAuthenticated} /> : <Navigate to="/dashboard" />}
        />
        <Route path="/dashboard" element={<PrivateRoute element={<Dashboard setAuth={setIsAuthenticated} />} />} />
        <Route path="/control"   element={<PrivateRoute element={<Control   setAuth={setIsAuthenticated} />} />} />
        <Route path="/noticias"  element={<PrivateRoute element={<Noticias  setAuth={setIsAuthenticated} />} />} />
        <Route path="/" element={<Navigate to="/control" />} />
      </Routes>
    </Router>
  );
}

export default App;
