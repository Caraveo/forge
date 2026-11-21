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
        // Chat messages that must not offer to build anything.
        string[] smallTalk = {"hi", "Hi!", "hi forge", "hello there", "hey", "thanks", "thank you so much", "ok", "cool",
            "good morning", "how do I rig a model?", "what can you do", "can you help", "lol", "bye", "hii", "yo!", "test"};
        foreach (string text in smallTalk)
            if (Intent.Subject(text) != null) throw new Exception("small talk treated as an idea: " + text + " -> " + Intent.Subject(text));
        string[,] ideas = {
            {"a cozy cabin in the woods", "a cozy cabin in the woods"}, {"dragon", "dragon"},
            {"I am thinking about a forest house", "a forest house"}, {"maybe a rusty robot.", "a rusty robot"},
            {"hi, a red car", "hi, a red car"}
        };
        for (int i=0; i<ideas.GetLength(0); i++) {
            string actual=Intent.Subject(ideas[i,0]);
            if(actual!=ideas[i,1])throw new Exception(ideas[i,0]+" idea -> "+(actual??"null"));
        }
        Console.WriteLine("Command and conversation routing passed.");
        return 0;
    }
}
