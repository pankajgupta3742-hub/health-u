import { motion } from 'framer-motion';
import logo from '../assets/health-u-logo.png';

export default function Splash() {
  return (
    <motion.div
      className="splash"
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 0.6, ease: 'easeInOut' } }}
    >
      <div className="splash-inner">
        <motion.img
          src={logo}
          alt="Health-U"
          className="splash-logo"
          initial={{ scale: 0.6, opacity: 0, rotate: -8 }}
          animate={{ scale: 1, opacity: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 180, damping: 14 }}
        />
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          style={{ fontSize: '1.6rem', fontWeight: 800 }}
        >
          Health-U
        </motion.h1>
        <div className="splash-bar">
          <motion.span
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{ duration: 2.2, ease: 'easeInOut' }}
          />
        </div>
      </div>
    </motion.div>
  );
}
