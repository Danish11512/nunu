export type BadgeVariant = 'yes' | 'no' | 'tie' | 'dry_run' | 'live' | 'read_only' | 'info';

interface BadgeProps {
  variant: BadgeVariant;
  label: string;
  size?: 'sm' | 'md';
}

const variantStyles: Record<BadgeVariant, string> = {
  yes: 'bg-green-800 text-green-200',
  no: 'bg-red-800 text-red-200',
  tie: 'bg-yellow-700 text-yellow-200',
  dry_run: 'bg-amber-800 text-amber-200',
  live: 'bg-green-800 text-green-200',
  read_only: 'bg-gray-700 text-gray-300',
  info: 'bg-blue-800 text-blue-200',
};

const sizeStyles = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
};

export default function Badge({ variant, label, size = 'sm' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded font-semibold ${variantStyles[variant]} ${sizeStyles[size]}`}>
      {label}
    </span>
  );
}
