using System;
internal static class CheckRouting {
    public static int Main() {
        string[,] cases = {
            {"forge a boat", "model"}, {"build a house", "model"}, {"make a dog", "model"}, {"mold a knight helmet", "model"}, {"Mold a dragon", "model"},
            {"generate a boat", "image"}, {"create a dog", "image"}, {"imagine a cat", "image"},
            {"please remove the background", "background"}, {"could you upscale it", "upscale"},
            {"can you rig it", "rig"}, {"hello", "chat"}, {"how do I rig a model?", "chat"},
            {"do not generate anything", "chat"}, {"make sure this works", "chat"},
            {"I am thinking about a forest house", "chat"}
        };
        for (int i=0; i<cases.GetLength(0); i++) {
            string actual=Intent.Mode(cases[i,0]);
            if(actual!=cases[i,1])throw new Exception(cases[i,0]+" routed to "+actual);
        }
        string[,] quality = {
            {"forge me a super apple", "high"}, {"mold a premium sword", "high"}, {"build a high-quality chair", "high"},
            {"make a prime steak", "high"}, {"forge a superior helmet", "high"}, {"generate a detailed castle", "high"},
            {"forge a draft barrel", "draft"}, {"make a low quality crate", "draft"}, {"forge a barrel", "standard"},
            {"build a superhero statue", "standard"}, {"forge a qualityless rock", "standard"}
        };
        for (int i=0; i<quality.GetLength(0); i++) {
            string actual=Intent.Quality(quality[i,0]);
            if(actual!=quality[i,1])throw new Exception(quality[i,0]+" quality "+actual);
        }
        Console.WriteLine("Command and conversation routing passed.");
        return 0;
    }
}
