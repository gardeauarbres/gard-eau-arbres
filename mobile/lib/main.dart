import 'package:flutter/material.dart';
import 'onboarding/onboarding_screen.dart';
import 'quiz/quiz_screen.dart';
import 'profile/profile_screen.dart';

void main() => runApp(const MyApp());

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gard Eau Arbres',
      theme: ThemeData(primarySwatch: Colors.green),
      home: const OnboardingScreen(),
      routes: {
        '/quiz': (_) => const QuizScreen(),
        '/profile': (_) => const ProfileScreen(),
      },
    );
  }
}
