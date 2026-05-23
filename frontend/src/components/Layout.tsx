import {
  Box,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
} from '@mui/material';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import ForumOutlinedIcon from '@mui/icons-material/ForumOutlined';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import MonitorHeartOutlinedIcon from '@mui/icons-material/MonitorHeartOutlined';
import ScheduleOutlinedIcon from '@mui/icons-material/ScheduleOutlined';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import { NavLink, Outlet, useLocation } from 'react-router-dom';

const drawerWidth = 260;

const navItems = [
  { to: '/', label: 'Agents', icon: SmartToyOutlinedIcon, end: true },
  { to: '/workflows', label: 'Workflows', icon: AccountTreeOutlinedIcon },
  { to: '/schedules', label: 'Schedules', icon: ScheduleOutlinedIcon },
  { to: '/monitor', label: 'Live Monitor', icon: MonitorHeartOutlinedIcon },
  { to: '/history', label: 'Message History', icon: ForumOutlinedIcon },
];

export default function Layout() {
  const location = useLocation();

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            borderRight: '1px solid',
            borderColor: 'divider',
            background: 'linear-gradient(180deg, #0f172a 0%, #111827 45%, #0b1220 100%)',
          },
        }}
      >
        <Toolbar sx={{ px: 2.5, py: 2, minHeight: 88 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 2,
                display: 'grid',
                placeItems: 'center',
                background: 'linear-gradient(135deg, #0284c7 0%, #6366f1 100%)',
                boxShadow: '0 8px 24px rgba(56, 189, 248, 0.25)',
              }}
            >
              <HubOutlinedIcon sx={{ color: 'white', fontSize: 22 }} />
            </Box>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
                Yuno
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Agent Platform
              </Typography>
            </Box>
          </Box>
        </Toolbar>

        <List sx={{ px: 1.5, py: 1 }}>
          {navItems.map(({ to, label, icon: Icon, end }) => {
            const active = end ? location.pathname === to : location.pathname.startsWith(to);
            return (
              <ListItemButton
                key={to}
                component={NavLink}
                to={to}
                end={end}
                sx={{
                  mb: 0.75,
                  borderRadius: 2,
                  color: active ? 'primary.light' : 'text.secondary',
                  bgcolor: active ? 'rgba(56, 189, 248, 0.12)' : 'transparent',
                  border: active ? '1px solid rgba(56, 189, 248, 0.25)' : '1px solid transparent',
                  '&:hover': {
                    bgcolor: active ? 'rgba(56, 189, 248, 0.16)' : 'rgba(148, 163, 184, 0.08)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40, color: active ? 'primary.main' : 'text.secondary' }}>
                  <Icon fontSize="small" />
                </ListItemIcon>
                <ListItemText
                  primary={label}
                  slotProps={{ primary: { sx: { fontWeight: active ? 600 : 500, fontSize: '0.95rem' } } }}
                />
              </ListItemButton>
            );
          })}
        </List>

        <Box sx={{ mt: 'auto', p: 2.5 }}>
          <Typography variant="caption" color="text.secondary">
            LangGraph orchestration · Live monitoring
          </Typography>
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 4 }, overflow: 'auto' }}>
        <Outlet />
      </Box>
    </Box>
  );
}
