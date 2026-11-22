import type { Metadata } from 'next';
import Workspace from '../../components/Workspace';
export const dynamic='force-dynamic';
export const metadata: Metadata = {
  title: 'Workspace · ParkMyCar',
  description: 'Operator and moderation workspace for ParkMyCar listings and reviews.'
};
export default function WorkspacePage(){return <Workspace/>;}
