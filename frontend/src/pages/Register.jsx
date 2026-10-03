import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { registerUser } from '../services/api';

function Register() {
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    setError('');
    setLoading(true);

    try {
      await registerUser(email, password);
      navigate('/login');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container-fluid min-vh-100 d-flex align-items-center justify-content-center bg-light">
      <div className="card shadow-sm border-0 p-4" style={{ maxWidth: '420px', width: '100%' }}>
        <div className="text-center mb-4">
          <h1 className="h3 fw-bold">VBC Things</h1>
          <p className="text-muted mb-0">Create your learning account</p>
        </div>

        <h2 className="h5 mb-3">Create account</h2>

        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label htmlFor="register-email" className="form-label">
              Email
            </label>

            <input
              id="register-email"
              type="email"
              className="form-control"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>

          <div className="mb-3">
            <label htmlFor="register-password" className="form-label">
              Password
            </label>

            <input
              id="register-password"
              type="password"
              className="form-control"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-dark w-100"
            disabled={loading}
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="text-center text-muted mt-4 mb-0">
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}

export default Register;

// FILE PURPOSE:
// Provides the VBC Things account registration interface.