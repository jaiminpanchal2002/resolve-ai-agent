import React, { useState } from "react";
import { Lock, Mail, UserPlus, Shield } from "lucide-react";

function Auth({ setToken, setRole }) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [roleSelection, setRoleSelection] = useState("reviewer");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage("");

    if (isLogin) {
      // Login flow
      try {
        const formData = new URLSearchParams();
        formData.append("username", email);
        formData.append("password", password);

        const response = await fetch("/api/auth/token", {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: formData,
        });

        const data = await response.json();
        if (response.ok) {
          setToken(data.access_token);
          setRole(data.role);
        } else {
          setMessage(data.detail || "Authentication failed");
        }
      } catch (err) {
        setMessage("Connection error. Is API running?");
      }
    } else {
      // Register flow
      try {
        const response = await fetch("/api/auth/register", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: json_stringify({
            email: email,
            password: password,
            role: roleSelection,
          }),
        });

        const data = await response.json();
        if (response.ok) {
          setMessage("Registration successful! Please log in.");
          setIsLogin(true);
        } else {
          setMessage(data.detail || "Registration failed");
        }
      } catch (err) {
        setMessage("Connection error.");
      }
    }
    setLoading(false);
  };

  // Helper because JSX doesn't like JSON.stringify without escapes sometimes
  function json_stringify(obj) {
    return JSON.stringify(obj);
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'radial-gradient(circle at top right, rgba(99, 102, 241, 0.15) 0%, var(--bg-main) 70%)',
      padding: '1.5rem'
    }}>
      <div class="glass-card" style={{
        maxWidth: '440px',
        width: '100%',
        padding: '2.5rem',
        textAlign: 'center'
      }}>
        <div style={{
          fontSize: '3rem',
          marginBottom: '1rem',
          animation: 'pulse 3s infinite'
        }}>🛡️</div>
        
        <h2 style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          marginBottom: '0.5rem',
          background: 'linear-gradient(135deg, #FFF 30%, var(--text-secondary) 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent'
        }}>
          {isLogin ? "ResolveAI Gatekeeper" : "Create Reviewer Profile"}
        </h2>
        
        <p style={{
          color: 'var(--text-secondary)',
          fontSize: '0.9rem',
          marginBottom: '2rem'
        }}>
          {isLogin ? "Sign in to audit customer support operations" : "Configure new system operator credentials"}
        </p>

        {message && (
          <div style={{
            background: message.includes("successful") ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)",
            color: message.includes("successful") ? "var(--success)" : "var(--danger)",
            padding: '0.8rem',
            borderRadius: '6px',
            fontSize: '0.85rem',
            marginBottom: '1.5rem',
            border: `1px solid ${message.includes("successful") ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`
          }}>
            {message}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ textAlign: 'left' }}>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              marginBottom: '0.5rem',
              fontWeight: 500
            }}>Operator Email</label>
            <div style={{ position: 'relative' }}>
              <Mail size={16} style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-secondary)'
              }} />
              <input
                type="email"
                required
                class="form-input"
                style={{ paddingLeft: '38px' }}
                placeholder="operator@resolveai.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{
              display: 'block',
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              marginBottom: '0.5rem',
              fontWeight: 500
            }}>Secure Password</label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-secondary)'
              }} />
              <input
                type="password"
                required
                class="form-input"
                style={{ paddingLeft: '38px' }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          {!isLogin && (
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{
                display: 'block',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                marginBottom: '0.5rem',
                fontWeight: 500
              }}>Select Role</label>
              <div style={{ position: 'relative' }}>
                <Shield size={16} style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-secondary)'
                }} />
                <select
                  class="form-input"
                  style={{ paddingLeft: '38px' }}
                  value={roleSelection}
                  onChange={(e) => setRoleSelection(e.target.value)}
                >
                  <option value="reviewer">Reviewer (Auditor)</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            </div>
          )}

          <button
            type="submit"
            class="btn"
            disabled={loading}
            style={{ width: '100%', justifyContent: 'center', padding: '0.75rem', fontSize: '0.95rem' }}
          >
            {loading ? "Authenticating..." : isLogin ? "Access System" : "Create Operator Account"}
          </button>
        </form>

        <div style={{ marginTop: '1.5rem', fontSize: '0.85rem' }}>
          <span style={{ color: 'var(--text-secondary)' }}>
            {isLogin ? "Need a reviewer access?" : "Already have operator profile?"}
          </span>{" "}
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setMessage("");
            }}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--primary)',
              cursor: 'pointer',
              fontWeight: 600,
              padding: 0
            }}
          >
            {isLogin ? "Register here" : "Sign in here"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default Auth;
