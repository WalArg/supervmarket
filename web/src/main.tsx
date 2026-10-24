import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { LocationProvider } from './location/LocationContext.tsx'
import { CartProvider } from './cart/CartContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LocationProvider>
      <CartProvider>
        <App />
      </CartProvider>
    </LocationProvider>
  </StrictMode>,
)
