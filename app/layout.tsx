import type { Metadata } from 'next';
import './globals.css';
import 'leaflet/dist/leaflet.css';
export const metadata:Metadata={title:'ParkMyCar — Park near your plans',description:'Search real places across India, open directions and compare sourced parking listings. Parking catalogue starts in Connaught Place, New Delhi.',applicationName:'ParkMyCar',manifest:'/manifest.webmanifest',icons:{icon:'/icon.svg',apple:'/icon.svg'}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to content</a>{children}</body></html>;}
