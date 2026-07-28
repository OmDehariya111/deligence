import Link from "next/link";

export default function NotFound() {
  return <main className="flex min-h-[70vh] items-center justify-center bg-black px-6 text-center text-white"><div><p className="text-sm font-semibold text-emerald-300">404</p><h1 className="mt-2 text-3xl font-bold">This page does not exist</h1><Link href="/" className="mt-6 inline-block rounded-lg bg-white px-4 py-2 text-sm font-semibold text-black">Return to DeligenX</Link></div></main>;
}
