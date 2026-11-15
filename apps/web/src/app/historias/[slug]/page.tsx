import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Story } from "@/components/stories/Story";
import story from "@/stories/trujillo-el-nino.json";

export function generateStaticParams() {
  return [{ slug: story.slug }];
}

export const metadata: Metadata = { title: `${story.title} · Historias` };

export default async function StoryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  if (slug !== story.slug) notFound();
  return <Story />;
}
