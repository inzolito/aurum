import React, { useState } from 'react';
import axios from 'axios';
import { Lock, User, AlertCircle, Loader } from 'lucide-react';

const Login = ({ setAuth }) => {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await axios.post(`/api/auth/login`, {
                username,
                password
            });
            
            localStorage.setItem('token', response.data.access_token);
            setAuth(true);
        } catch (err) {
            setError(err.response?.data?.detail || 'Error de conexión con el servidor');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-header">
                    <div className="prism-logo">▽</div>
                    <h1>AURUM PRISM</h1>
                    <p>Terminal de Acceso Operativo</p>
                </div>

                <form onSubmit={handleSubmit} className="login-form">
                    {error && (
                        <div className="error-message">
                            <AlertCircle size={18} />
                            <span>{error}</span>
                        </div>
                    )}

                    <div className="input-group">
                        <label htmlFor="username">Usuario</label>
                        <div className="input-wrapper">
                            <User className="input-icon" size={20} />
                            <input
                                id="username"
                                type="text"
                                placeholder="Ingresar identificador"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <div className="input-group">
                        <label htmlFor="password">Contraseña</label>
                        <div className="input-wrapper">
                            <Lock className="input-icon" size={20} />
                            <input
                                id="password"
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                    </div>

                    <button type="submit" className="login-button" disabled={loading}>
                        {loading ? (
                            <Loader className="animate-spin" size={20} />
                        ) : (
                            'INICIAR SESIÓN'
                        )}
                    </button>
                </form>

                <div className="login-footer">
                    <span>v1.0.0 Prism Base</span>
                </div>
            </div>
        </div>
    );
};

export default Login;
