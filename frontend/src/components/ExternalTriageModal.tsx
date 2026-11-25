import Modal from './Modal';

// Third-party triage tool kept from the original app. It is shown only when the
// user chooses it explicitly.
export default function ExternalTriageModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} title="External triage tool" onClose={onClose} wide>
      <iframe
        className="external-frame"
        src="https://smart-triage-buddy-94.lovable.app"
        title="External triage tool"
      />
    </Modal>
  );
}
